#!/usr/bin/env python3
"""
Automatically scan directory and translate non-English text files.
Optimized for Python 3.12.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Final

from deep_translator import GoogleTranslator

# Configuration
DIRECTORY: Final[str] = "."
CHUNK_SIZE: Final[int] = 2000
MAX_WORKERS_FILE: Final[int] = 6
MAX_WORKERS_CHUNK: Final[int] = 8
ZERO_DOT_THREE: Final[float] = 0.3

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Try to import fastwalk
try:
    from fastwalk import walk_files
    HAS_FASTWALK = True
except ImportError:
    HAS_FASTWALK = False

NON_ENGLISH_PATTERN: Final[re.Pattern] = re.compile(r"[^\x00-\x7F]")

def is_binary(path: Path) -> bool:
    """Detects if a file is binary by checking for null bytes and non-text ratio."""
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        
        # Standard printable ASCII + common whitespace
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        non_text_count = sum(1 for b in chunk if b not in text_chars)
        return (non_text_count / len(chunk)) > ZERO_DOT_THREE
    except Exception:
        return True

def split_into_chunks(text: str, size: int) -> list[str]:
    """Splits a string into equal sized chunks."""
    return [text[i : i + size] for i in range(0, len(text), size)]

def translate_chunk(chunk: str) -> str:
    """Translates a single chunk of text."""
    if not chunk.strip():
        return chunk
    try:
        return GoogleTranslator(source="auto", target="en").translate(chunk)
    except Exception as e:
        logger.error("Chunk translation failed: %s", e)
        return chunk

def contains_non_english(text: str) -> bool:
    """Checks if text contains any non-English characters."""
    return bool(NON_ENGLISH_PATTERN.search(text))

def translate_file(path: Path) -> None:
    """Reads, translates in chunks, and writes a new English version of a file."""
    logger.info("Processing file: %s", path)
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.error("Cannot read file %s: %s", path, e)
        return

    if not contains_non_english(content):
        logger.info("File is already English: %s", path.name)
        return

    logger.info("Non-English content detected in: %s", path.name)
    chunks = split_into_chunks(content, CHUNK_SIZE)
    logger.info("Total chunks: %d. Translating in parallel...", len(chunks))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS_CHUNK) as executor:
        translated_chunks = list(executor.map(translate_chunk, chunks))

    translated_text = "".join(translated_chunks)
    new_path = path.with_stem(f"{path.stem}_eng")
    
    try:
        new_path.write_text(translated_text, encoding="utf-8")
        logger.info("\u2713 Translated \u2192 %s", new_path.name)
    except Exception as e:
        logger.error("Failed to write output file %s: %s", new_path, e)

def process_directory(directory: str) -> None:
    """Scans directory for text files and initiates parallel translation."""
    logger.info("Scanning directory: %s", directory)
    dir_path = Path(directory)
    
    files: list[Path] = []
    
    if HAS_FASTWALK:
        for pth in walk_files(directory):
            p = Path(pth)
            if p.is_file() and not is_binary(p):
                files.append(p)
    else:
        # Fallback to standard library
        for p in dir_path.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.parts) and not is_binary(p):
                files.append(p)

    logger.info("Total text files found: %d", len(files))
    if not files:
        return

    logger.info("Starting parallel file translation...\n")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_FILE) as executor:
        futures = {executor.submit(translate_file, f): f for f in files}
        for future in as_completed(futures):
            f = futures[future]
            try:
                future.result()
            except Exception as e:
                logger.error("Unexpected error processing %s: %s", f, e)

if __name__ == "__main__":
    process_directory(DIRECTORY)
