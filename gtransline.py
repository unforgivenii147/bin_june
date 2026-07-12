#!/usr/bin/env python3
"""
Translate non-English lines (focused on Chinese) to English in-place.
Optimized for Python 3.12.
"""

import argparse
import logging
import multiprocessing as mp
import re
import sys
from pathlib import Path
from typing import Final

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Try to import translators
try:
    from googletrans import Translator

    HAS_GOOGLETRANS = True
except ImportError:
    HAS_GOOGLETRANS = False

try:
    from deep_translator import GoogleTranslator

    HAS_DEEP_TRANSLATOR = True
except ImportError:
    HAS_DEEP_TRANSLATOR = False

if not (HAS_GOOGLETRANS or HAS_DEEP_TRANSLATOR):
    logger.error("Please install either googletrans (4.0.0rc1) or deep-translator.")
    sys.exit(1)

# Configuration
SKIP_DIRS: Final[frozenset[str]] = frozenset({
    "lazy",
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
})

# Comprehensive Chinese character regex
CHINESE_PATTERN: Final[re.Pattern] = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\u20000-\u2a6df\u2a700-\u2b73f\u2b740-\u2b81f\u2b820-\u2ceaf\uf900-\ufaff]"
)


def is_chinese_text(text: str, threshold: float = 0.3) -> bool:
    """Checks if text contains a significant portion of Chinese characters."""
    clean_text = "".join(text.split())
    if not clean_text:
        return False

    chinese_chars = len(CHINESE_PATTERN.findall(clean_text))
    return (chinese_chars / len(clean_text)) >= threshold


def is_non_english(text: str) -> bool:
    """Heuristic to determine if a line needs translation."""
    if not text.strip():
        return False
    return is_chinese_text(text)


class UniversalTranslator:
    """Wrapper for available translation libraries."""

    def __init__(self):
        if HAS_DEEP_TRANSLATOR:
            self.translator = GoogleTranslator(source="auto", target="en")
            self.mode = "deep"
        else:
            self.translator = Translator()
            self.mode = "google"

    def translate(self, text: str) -> str:
        if not text.strip():
            return text
        try:
            if self.mode == "deep":
                return self.translator.translate(text)
            else:
                return self.translator.translate(text, dest="en").text
        except Exception as e:
            logger.warning("Translation error: %s", e)
            return text


def process_file(file_path: Path, batch_size: int = 10) -> None:
    """Translates non-English lines in a file in-place."""
    logger.info("Processing: %s", file_path)
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = source.splitlines(keepends=True)

        target_indices = [i for i, line in enumerate(lines) if is_non_english(line)]

        if not target_indices:
            logger.info("  No non-English (Chinese) lines found, skipping.")
            return

        translator = UniversalTranslator()
        translated_count = 0

        for i, idx in enumerate(target_indices):
            line = lines[idx]
            leading_ws = line[: len(line) - len(line.lstrip())]
            trailing_ws = line[len(line.rstrip()) :]
            stripped_line = line.strip()

            translated = translator.translate(stripped_line)
            lines[idx] = f"{leading_ws}{translated}{trailing_ws}"
            translated_count += 1

            if (i + 1) % batch_size == 0:
                logger.info("  Progress: %d/%d lines translated", i + 1, len(target_indices))

        file_path.write_text("".join(lines), encoding="utf-8", errors="ignore")
        logger.info("  \u2713 Completed: %d lines translated", translated_count)

    except Exception as e:
        logger.error("  \u2717 Error processing %s: %s", file_path, e)


def worker(args: tuple[Path, int]) -> None:
    """Worker function for pool mapping."""
    process_file(*args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate non-English (Chinese) lines in-place.")
    parser.add_argument("files", nargs="+", help="Files or directories to process")
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".csv"],
        help="File extensions to process",
    )
    parser.add_argument(
        "--workers", type=int, default=mp.cpu_count(), help=f"Number of parallel workers (default: {mp.cpu_count()})"
    )
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for progress logging")
    parser.add_argument("--exclude", nargs="+", default=[], help="Paths to exclude")

    args = parser.parse_args()
    exclude_paths = {Path(p).resolve() for p in args.exclude}

    files_to_process: list[Path] = []
    for entry in args.files:
        path = Path(entry)
        if path.is_file():
            if path.resolve() not in exclude_paths:
                files_to_process.append(path)
        elif path.is_dir():
            for ext in args.extensions:
                for file_path in path.rglob(f"*{ext}"):
                    if (
                        file_path.is_file()
                        and file_path.resolve() not in exclude_paths
                        and not any(part.startswith(".") for part in file_path.parts)
                    ):
                        files_to_process.append(file_path)

    if not files_to_process:
        logger.info("No files to process.")
        return

    logger.info("Found %d files. Using %d workers...", len(files_to_process), args.workers)

    tasks = [(fp, args.batch_size) for fp in files_to_process]

    if args.workers == 1:
        for t in tasks:
            worker(t)
    else:
        with mp.Pool(processes=args.workers) as pool:
            pool.map(worker, tasks)

    logger.info("\n\u2713 All translations completed!")


if __name__ == "__main__":
    main()
