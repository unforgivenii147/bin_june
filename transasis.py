#!/data/data/com.termux/files/usr/bin/env python


"""
Optimized version of transasis.py for Python 3.12.
Translates text files to English recursively or individually.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Final, Iterator

from deep_translator import GoogleTranslator

CHUNK_SIZE: Final[int] = 2000
TARGET_LANGUAGE: Final[str] = "en"
SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
)
NON_ENGLISH_PATTERN: Final[re.Pattern] = re.compile("[^\\x00-\\x7F]")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = 32768) -> Iterator[str]:
    words = text.split()
    for i in range(0, len(words), chunk_size):
        yield " ".join(words[i : i + chunk_size])


def translate_text(text: str) -> str:
    try:
        translator = GoogleTranslator(source="auto", target=TARGET_LANGUAGE)
        return translator.translate(text)
    except Exception as e:
        logger.error("Error translating text chunk: %s", e)
        return text


def translate_file(filepath: Path) -> None:
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Skipping unreadable file %s: %s", filepath, e)
        return
    if not NON_ENGLISH_PATTERN.search(content):
        logger.info("No non-English content found in %s, skipping.", filepath.name)
        return
    logger.info("Translating: %s", filepath.name)
    translated_chunks = [translate_text(chunk) for chunk in chunk_text(content)]
    translated_content = "\n\n".join(translated_chunks)
    new_filepath = filepath.parent / f"translated_{filepath.name}"
    try:
        new_filepath.write_text(translated_content, encoding="utf-8")
        logger.info("✓ Saved as: %s", new_filepath.name)
    except Exception as e:
        logger.error("Error writing to %s: %s", new_filepath, e)


def translate_folder(directory: Path) -> None:
    for p in directory.rglob("*"):
        if any(part.startswith(".") or part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            translate_file(p)


def main() -> None:
    choice = input("Translate a (f)ile or (d)irectory? ").lower().strip()
    if choice == "d":
        translate_folder(Path("."))
    elif choice == "f":
        fn = input("Filename: ").strip()
        path = Path(fn)
        if path.exists():
            translate_file(path)
        else:
            logger.error("File not found: %s", fn)
    else:
        logger.error("Invalid choice. Enter 'd' for directory and 'f' for file.")
        sys.exit(1)


if __name__ == "__main__":
    main()
