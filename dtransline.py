#!/data/data/com.termux/files/usr/bin/env python


"""
Alternative version using deep-translator for translation.
Requires: deep-translator
"""

import argparse
import multiprocessing as mp
from pathlib import Path
from typing import List, Tuple
import sys
import time

try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("Please install deep-translator: pip install deep-translator")
    sys.exit(1)


def is_english(text: str) -> bool:
    text = text.strip()
    if not text:
        return True
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return True
    ascii_alpha = sum((1 for c in alpha_chars if ord(c) < 128))
    return ascii_alpha / len(alpha_chars) > 0.6


def translate_text(text: str, translator: GoogleTranslator, max_retries: int = 3) -> str:
    if not text.strip() or is_english(text):
        return text
    for attempt in range(max_retries):
        try:
            translated = translator.translate(text)
            return translated
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                print(f"Translation failed after {max_retries} attempts: {e}", file=sys.stderr)
                return text


def process_file(file_path: Path) -> None:
    print(f"Processing: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        translator = GoogleTranslator(source="auto", target="en")
        translated_count = 0
        translated_lines = []
        for i, line in enumerate(lines):
            if line.strip() and (not is_english(line)):
                leading_ws = line[: len(line) - len(line.lstrip())]
                trailing_ws = line[len(line.rstrip()) :]
                stripped_line = line.strip()
                translated_text = translate_text(stripped_line, translator)
                translated_lines.append(leading_ws + translated_text + trailing_ws)
                translated_count += 1
                if translated_count % 10 == 0:
                    print(f"  Progress: {translated_count} lines translated")
            else:
                translated_lines.append(line)
        if translated_count == 0:
            print(f"  No non-English lines found, skipping.")
            return
        with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
            f.writelines(translated_lines)
        print(f"  ✓ Completed: {translated_count} lines translated")
    except Exception as e:
        print(f"  ✗ Error processing {file_path}: {e}", file=sys.stderr)


def worker(file_path: Path) -> None:
    process_file(file_path)


def main():
    parser = argparse.ArgumentParser(description="Translate non-English lines in files to English in-place")
    parser.add_argument("files", nargs="+", type=str, help="Files or directories to process")
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".csv"],
        help="File extensions to process",
    )
    parser.add_argument(
        "--workers", type=int, default=mp.cpu_count(), help=f"Number of parallel workers (default: {mp.cpu_count()})"
    )
    parser.add_argument("--exclude", nargs="+", default=[], help="Files or directories to exclude")
    args = parser.parse_args()
    files_to_process = []
    exclude_paths = [Path(p).resolve() for p in args.exclude]
    for file_pattern in args.files:
        path = Path(file_pattern)
        if path.is_file():
            if path.resolve() not in exclude_paths:
                if path.suffix in args.extensions:
                    files_to_process.append(path)
        elif path.is_dir():
            for ext in args.extensions:
                for file_path in path.rglob(f"*{ext}"):
                    if file_path.is_file() and file_path.resolve() not in exclude_paths:
                        if not any((part.startswith(".") for part in file_path.parts)):
                            files_to_process.append(file_path)
        else:
            print(f"Warning: {path} does not exist", file=sys.stderr)
    if not files_to_process:
        print("No files to process.")
        return
    print(f"Found {len(files_to_process)} files to process")
    print(f"Using {args.workers} workers\n")
    if args.workers == 1:
        for file_path in files_to_process:
            worker(file_path)
    else:
        with mp.Pool(processes=args.workers) as pool:
            pool.map(worker, files_to_process)
    print("\n✓ All translations completed!")


if __name__ == "__main__":
    main()
