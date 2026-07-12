#!/data/data/com.termux/files/usr/bin/env python
import io
import re
import shutil
import sys
import tempfile
import tokenize
from pathlib import Path

from deep_translator import GoogleTranslator


from pathlib import Path
from typing import Any, ParamSpec, TypeVar
from collections.abc import Callable, Iterable
from os import scandir as os_scandir
from multiprocessing import get_context


def mpf_async(func: Callable[[Any], Any], items: Iterable[Any]):
    with get_context("spawn").Pool(MAX_WORKERS) as p:
        async_results = [p.apply_async(func, (item,)) for item in items]
        results = []
        for i, async_result in enumerate(async_results):
            try:
                results.append(async_result.get(timeout=30))
            except Exception as e:
                print(f"Item {i} failed: {e}")
                results.append(None)
        return results


def is_binary(path: (Path | str)) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def get_nobinary(path: (str | Path)) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


cwd = Path.cwd()
non_english_pattern = re.compile(r"[^\x00-\x7F]")


def is_english(text: str) -> bool:
    return not non_english_pattern.search(text)


def batch_translate(texts: list[str]) -> list[str]:
    """Translates a list of strings efficiently by joining them with a unique separator."""
    if not texts:
        return []

    # Use a safe delimiter that Google Translator won't corrupt
    separator = "\n===|||===\n"
    combined_text = separator.join(texts)

    try:
        translated_combined = GoogleTranslator(source="auto", target="en").translate(combined_text)
        if not translated_combined:
            return texts

        # Split back by the same delimiter, stripping any extra whitespace added by the translator
        translated_list = [t.strip() for t in translated_combined.split(separator.strip())]

        # Fallback if the translator messed up the structure
        if len(translated_list) != len(texts):
            print(
                f"  Warning: Batch mismatch ({len(translated_list)} vs {len(texts)}). Falling back to individual translation."
            )
            return [GoogleTranslator(source="auto", target="en").translate(t) or t for t in texts]

        return translated_list
    except Exception as e:
        print(f"  Batch translation error: {e}")
        return texts


def safe_overwrite(filepath: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=filepath.parent) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    shutil.move(tmp_path, filepath)


def translate_python_file(source: str) -> str:
    print("  Analyzing Python structure...")

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        # Fallback to plain text translation if tokenization completely fails
        return batch_translate([source])[0]

    to_translate = []
    translation_targets = []  # Keeps track of token index and structural type

    # First pass: Identify and collect all candidates for translation
    for idx, token in enumerate(tokens):
        tok_type, tok_str = token[0], token[1]

        if tok_type == tokenize.COMMENT and not is_english(tok_str):
            comment_text = tok_str[1:].strip()
            if comment_text:
                to_translate.append(comment_text)
                translation_targets.append((idx, "COMMENT"))

        elif tok_type == tokenize.STRING:
            stripped = tok_str.strip("'\"")
            if stripped and not is_english(stripped) and len(stripped) > 10:
                to_translate.append(stripped)
                translation_targets.append((idx, "STRING", tok_str))

    if not to_translate:
        return source

    print(f"  Batch translating {len(to_translate)} items...")
    translated_texts = batch_translate(to_translate)

    # Second pass: Map the translated elements back onto the original tokens
    for target_info, translated_str in zip(translation_targets, translated_texts):
        idx = target_info[0]
        tok_type = target_info[1]

        if tok_type == "COMMENT":
            tokens[idx] = (tokenize.COMMENT, f"# {translated_str}") + tokens[idx][2:]
        elif tok_type == "STRING":
            orig_tok_str = target_info[2]
            if orig_tok_str.startswith((DOC_TH1, DOC_TH2)):
                quote_char = orig_tok_str[:3]
            else:
                quote_char = orig_tok_str[0]

            # Reconstruct string with original outer quotes
            tokens[idx] = (tokenize.STRING, f"{quote_char}{translated_str}{quote_char}") + tokens[idx][2:]

    try:
        return tokenize.untokenize(tokens).decode("utf-8")
    except Exception as e:
        print(f"  Error rebuilding python file structure: {e}")
        return source


def process_file(path: str | Path) -> None:
    path = Path(path)
    try:
        original = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"  Error reading {path}: {e}")
        return

    if is_english(original.strip()):
        return

    print(f"  Processing {path.name}...")
    try:
        if path.suffix == ".py":
            translated = translate_python_file(original)
        else:
            translated = batch_translate([original])[0]

        if translated.strip() != original.strip():
            safe_overwrite(path, translated)
            print(f"  ✓ Updated {path.name}")
    except Exception as e:
        print(f"  Failed to process {path}: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_nobinary(cwd)
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    mpf_async(process_file, files)
