#!/usr/bin/env python3
"""
Optimized version of ultratranslator.py for Python 3.12.
Translates Python files and other text files while preserving structure.
"""

import ast
import io
import logging
import re
import shutil
import sys
import tempfile
import tokenize
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from os import scandir
from pathlib import Path
from typing import Any, Final

from deep_translator import GoogleTranslator
from binaryornot import is_binary

# Constants
CHUNK_SIZE: Final[int] = 4990
SKIP_DIRS: Final[frozenset[str]] = frozenset({".git", "__pycache__", ".venv"})
MAX_WORKERS: Final[int] = 6
DOC_TH1: Final[str] = '"""'
DOC_TH2: Final[str] = "'''"

# Regex for non-English detection
NON_ENGLISH_PATTERN: Final[re.Pattern] = re.compile(r"[^\x00-\x7F]")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_english(text: str) -> bool:
    """Checks if the text is primarily English (ASCII)."""
    return not NON_ENGLISH_PATTERN.search(text)


def get_nobinary(path: Path) -> list[Path]:
    """Returns a list of non-binary files in the directory."""
    return [f for f in get_files(path) if not is_binary(str(f))]


def get_files(path: Path, include_hidden: bool = False, ext: tuple[str, ...] | None = None) -> list[Path]:
    """Recursively gets files from a directory, skipping specific folders."""
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


def translate_text(text: str) -> str:
    """Translates text using Google Translate."""
    try:
        translated = GoogleTranslator(source="auto", target="en").translate(text)
        return translated if translated else text
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text


def translate_file_content(path: Path) -> str:
    """Translates the entire content of a file."""
    try:
        return GoogleTranslator(source="auto", target="en").translate_file(str(path))
    except Exception as e:
        logger.error(f"Error translating file {path}: {e}")
        return path.read_text(encoding="utf-8", errors="ignore")


def safe_overwrite(filepath: Path, content: str) -> None:
    """Atomically overwrites a file with new content."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=filepath.parent) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    shutil.move(tmp_path, filepath)


def translate_python_file(path: Path) -> str:
    """Parses a Python file and translates comments and strings while preserving code structure."""
    logger.info(f"  Analyzing Python structure for {path.name}...")
    source = path.read_text(encoding="utf-8")
    
    try:
        # Check if it's a valid python file
        ast.parse(source)
    except SyntaxError as e:
        logger.warning(f"  Syntax error in {path.name}: {e}. Translating as plain text.")
        return translate_file_content(path)

    result = []
    translated_count = 0

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return translate_file_content(path)

    source_lines = source.splitlines(keepends=True)
    prev_end = (1, 0)

    for token in tokens:
        tok_type, tok_str, start, end, line = token

        # Fill in skipped text (whitespace, etc.)
        if start[0] > prev_end[0]:
            result.extend(source_lines[prev_end[0]:start[0]])
            result.append(line[:start[1]])
        elif start[1] > prev_end[1]:
            result.append(line[prev_end[1]:start[1]])

        if tok_type == tokenize.COMMENT and not is_english(tok_str):
            comment_text = tok_str[1:].strip()
            translated = translate_text(comment_text)
            result.append(f"# {translated}")
            translated_count += 1
        elif tok_type == tokenize.STRING:
            stripped = tok_str.strip("'\"")
            if stripped and not is_english(stripped) and len(stripped) > 5:
                translated = translate_text(stripped)
                quote_char = tok_str[:3] if tok_str.startswith((DOC_TH1, DOC_TH2)) else tok_str[0]
                result.append(f"{quote_char}{translated}{quote_char}")
                translated_count += 1
            else:
                result.append(tok_str)
        else:
            result.append(tok_str)
        
        prev_end = end

    logger.info(f"  Translated {translated_count} items in {path.name}")
    return "".join(result)


def process_file(path: Path) -> None:
    """Processes a single file based on its type."""
    logger.info(f"  Processing {path.name}...")
    try:
        original = path.read_text(encoding="utf-8", errors="ignore")
        if is_english(original):
            return

        if path.suffix == ".py":
            translated = translate_python_file(path)
        else:
            translated = translate_file_content(path)

        if translated.strip() != original.strip():
            safe_overwrite(path, translated)
            logger.info(f"  ✓ Updated {path.name}")
    except Exception as e:
        logger.error(f"  Failed to process {path}: {e}")


def main() -> None:
    """Main entry point using ProcessPoolExecutor for parallel processing."""
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_nobinary(Path.cwd())

    if not files:
        logger.info("No files found to process.")
        return

    logger.info(f"Found {len(files)} files to process.")

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        for future in as_completed(futures):
            f = futures[future]
            try:
                future.result()
            except Exception as e:
                logger.error(f"File {f} generated an exception: {e}")


if __name__ == "__main__":
    main()
