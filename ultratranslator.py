import ast
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


def chunk_text(text: str, size: int = 800) -> list[str]:
    if not text or size <= 0:
        return [text] if text else []
    chunks = []
    for i in range(0, len(text), size):
        chunks.append(text[i : i + size])
    return chunks


def translate_chunk(chunk: str) -> str:
    if not chunk or is_english(chunk):
        return chunk
    try:
        result = GoogleTranslator(source="auto", target="en").translate(chunk)
        print("*" * 35)
        print(result)
        print("*" * 35)
        return result if result else chunk
    except Exception as e:
        print(f"  Translation error: {e}")
        return chunk


def translate_text(text: str) -> str:
    if not text or is_english(text):
        return text
    chunks = chunk_text(text)
    return "".join(translate_chunk(chunk) for chunk in chunks)


def safe_overwrite(filepath: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=filepath.parent) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    shutil.move(tmp_path, filepath)


def translate_python_file(source: str) -> str:
    print("  Analyzing Python structure...")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"  Syntax error: {e}")
        return source

    result = []
    translated_count = 0

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return translate_text(source)

    source_lines = source.splitlines(keepends=True)
    prev_end = (1, 0)

    for token in tokens:
        tok_type, tok_str, start, end, line = token

        if start[0] > prev_end[0]:
            result.extend(source_lines[prev_end[0] : start[0]])
            result.append(line[: start[1]])
        elif start[1] > prev_end[1]:
            result.append(line[prev_end[1] : start[1]])

        if tok_type == tokenize.COMMENT and not is_english(tok_str):
            comment_text = tok_str[1:].strip()
            print(f"  Translating comment: {comment_text[:50]}...")
            translated = translate_text(comment_text)
            result.append(f"# {translated}")
            translated_count += 1

        elif tok_type == tokenize.STRING:
            stripped = tok_str.strip("'\"")
            if stripped and not is_english(stripped) and len(stripped) > 10:
                try:
                    print(f"  Translating string: {stripped[:50]}...")
                    translated = translate_text(stripped)

                    if tok_str.startswith((DOC_TH1, DOC_TH2)):
                        quote_char = tok_str[:3]
                    else:
                        quote_char = tok_str[0]

                    result.append(f"{quote_char}{translated}{quote_char}")
                    translated_count += 1
                except Exception as e:
                    print(f"  Error translating string: {e}")
                    result.append(tok_str)
            else:
                result.append(tok_str)
        else:
            result.append(tok_str)

        prev_end = end

    print(f"  Translated {translated_count} items")
    return "".join(result)


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
            translated = translate_text(original)

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
