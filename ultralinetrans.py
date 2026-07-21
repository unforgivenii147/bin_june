#!/data/data/com.termux/files/usr/bin/env python


"""
Optimized version of ultralinetrans.py for Python 3.12.
Translates files using batch translation for improved performance.
"""

from __future__ import annotations

import io
import logging
import re
import shutil
import sys
import tempfile
import tokenize
from concurrent.futures import ProcessPoolExecutor, as_completed
from os import scandir
from pathlib import Path
from typing import Final

from deep_translator import GoogleTranslator

CHUNK_SIZE = 1024 * 1024

CHUNK_SIZE: Final[int] = 4990
MAX_WORKERS: Final[int] = 6
DOC_TH1: Final[str] = '"""'
DOC_TH2: Final[str] = "'''"

SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".venv"}
)
NON_ENGLISH_PATTERN: Final[re.Pattern] = re.compile("[^\\x00-\\x7F]")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > 0.3
    except Exception:
        return True


def get_files(path: Path, include_hidden: bool = False, ext: tuple[str, ...] | None = None) -> list[Path]:
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")
    files = []
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue
    return sorted(files)


def is_english(text: str) -> bool:
    return not NON_ENGLISH_PATTERN.search(text)


def batch_translate(texts: list[str]) -> list[str]:
    if not texts:
        return []
    separator = "\n===|||===\n"
    combined_text = separator.join(texts)
    try:
        translated_combined = GoogleTranslator(source="auto", target="en").translate(combined_text)
        if not translated_combined:
            return texts
        translated_list = [t.strip() for t in translated_combined.split(separator.strip())]
        if len(translated_list) != len(texts):
            logger.warning(
                f"Batch mismatch ({len(translated_list)} vs {len(texts)}). Falling back to individual translation."
            )
            return [GoogleTranslator(source="auto", target="en").translate(t) or t for t in texts]
        return translated_list
    except Exception as e:
        logger.error(f"Batch translation error: {e}")
        return texts


def safe_overwrite(filepath: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=filepath.parent) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    shutil.move(tmp_path, filepath)


def translate_python_file(source: str) -> str:
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        return batch_translate([source])[0]
    to_translate = []
    translation_targets = []
    for idx, token in enumerate(tokens):
        tok_type, tok_str = (token[0], token[1])
        if tok_type == tokenize.COMMENT and (not is_english(tok_str)):
            comment_text = tok_str[1:].strip()
            if comment_text:
                to_translate.append(comment_text)
                translation_targets.append((idx, "COMMENT"))
        elif tok_type == tokenize.STRING:
            stripped = tok_str.strip("'\"")
            if stripped and (not is_english(stripped)) and (len(stripped) > 5):
                to_translate.append(stripped)
                translation_targets.append((idx, "STRING", tok_str))
    if not to_translate:
        return source
    translated_texts = batch_translate(to_translate)
    for target_info, translated_str in zip(translation_targets, translated_texts, strict=False):
        idx = target_info[0]
        tok_type = target_info[1]
        if tok_type == "COMMENT":
            tokens[idx] = (tokenize.COMMENT, f"# {translated_str}") + tokens[idx][2:]
        elif tok_type == "STRING":
            orig_tok_str = target_info[2]
            quote_char = orig_tok_str[:3] if orig_tok_str.startswith((DOC_TH1, DOC_TH2)) else orig_tok_str[0]
            tokens[idx] = (tokenize.STRING, f"{quote_char}{translated_str}{quote_char}") + tokens[idx][2:]
    try:
        return tokenize.untokenize(tokens).decode("utf-8")
    except Exception as e:
        logger.error(f"Error rebuilding python file structure: {e}")
        return source


def process_file(path: Path) -> None:
    try:
        original = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Error reading {path}: {e}")
        return
    if is_english(original.strip()):
        return
    logger.info(f"Processing {path.name}...")
    try:
        if path.suffix == ".py":
            translated = translate_python_file(original)
        else:
            translated = batch_translate([original])[0]
        if translated.strip() != original.strip():
            safe_overwrite(path, translated)
            logger.info(f"✓ Updated {path.name}")
    except Exception as e:
        logger.error(f"Failed to process {path}: {e}")


def main() -> None:
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else [f for f in get_files(Path.cwd()) if not is_binary(f)]
    if not files:
        logger.info("No files to process.")
        return
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Task failed: {e}")


if __name__ == "__main__":
    main()