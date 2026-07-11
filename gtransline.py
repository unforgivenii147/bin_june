#!/data/data/com.termux/files/usr/bin/env python


"""
Translate non-English lines in files to English in-place using parallel processing.
Requires: googletrans==4.0.0rc1 or deep-translator
"""

import argparse
import multiprocessing as mp
from pathlib import Path
from typing import List, Tuple
import re
import sys

try:
    from googletrans import Translator
except ImportError:
    print("Please install googletrans: pip install googletrans==4.0.0rc1")
    sys.exit(1)


def contains_chinese(text: str) -> bool:
    chinese_pattern = re.compile("[一-鿿㐀-䶿\u20000-⩭F⩰0-⭳F\u2b740-⮁F⮂0-⳪F豈-\ufaff⾀0-⾡F]")
    return bool(chinese_pattern.search(text))


def is_chinese_text(text: str, threshold: float = 0.3) -> bool:
    text = text.strip()
    if not text:
        return False
    total_chars = len([c for c in text if not c.isspace()])
    if total_chars == 0:
        return False
    chinese_chars = len(re.findall("[一-鿿㐀-䶿\u20000-⩭F⩰0-⭳F\u2b740-⮁F⮂0-⳪F豈-\ufaff⾀0-⾡F]", text))
    return chinese_chars / total_chars >= threshold


def is_english(text: str) -> bool:
    return not is_chinese_text(text)


def translate_line(line: str, translator: Translator) -> str:
    if not line.strip() or is_english(line):
        return line
    try:
        leading_ws = line[: len(line) - len(line.lstrip())]
        trailing_ws = line[len(line.rstrip()) :]
        stripped_line = line.strip()
        translated = translator.translate(stripped_line, dest="en").text
        return leading_ws + translated + trailing_ws
    except Exception as e:
        print(f"Translation error: {e}", file=sys.stderr)
        return line


def process_lines_batch(lines_with_indices: List[Tuple[int, str]], translator: Translator) -> List[Tuple[int, str]]:
    results = []
    for idx, line in lines_with_indices:
        if line.strip() and (not is_english(line)):
            translated_line = translate_line(line, translator)
            results.append((idx, translated_line))
        else:
            results.append((idx, line))
    return results


def process_file(file_path: Path, translator: Translator, batch_size: int = 10) -> None:
    print(f"Processing: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        needs_translation = False
        for line in lines:
            if line.strip() and (not is_english(line)):
                needs_translation = True
                break
        if not needs_translation:
            print(f"  No non-English lines found, skipping.")
            return
        translated_lines = lines.copy()
        non_english_indices = [(i, line) for i, line in enumerate(lines) if line.strip() and (not is_english(line))]
        for i, (idx, line) in enumerate(non_english_indices):
            translated_line = translate_line(line, translator)
            translated_lines[idx] = translated_line
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{len(non_english_indices)} lines translated")
        with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
            f.writelines(translated_lines)
        print(f"  ✓ Completed: {len(non_english_indices)} lines translated")
    except Exception as e:
        print(f"  ✗ Error processing {file_path}: {e}", file=sys.stderr)


def worker(args: Tuple[Path, int]) -> None:
    file_path, batch_size = args
    translator = Translator()
    process_file(file_path, translator, batch_size)


def main():
    parser = argparse.ArgumentParser(description="Translate non-English lines in files to English in-place")
    parser.add_argument("files", nargs="+", type=str, help="Files or directories to process")
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".csv"],
        help="File extensions to process (default: .txt .md .py .js .html .css .json .xml .csv)",
    )
    parser.add_argument(
        "--workers", type=int, default=mp.cpu_count(), help=f"Number of parallel workers (default: {mp.cpu_count()})"
    )
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for translation (default: 10)")
    parser.add_argument("--exclude", nargs="+", default=[], help="Files or directories to exclude")
    args = parser.parse_args()
    files_to_process = []
    exclude_paths = [Path(p).resolve() for p in args.exclude]
    for file_pattern in args.files:
        path = Path(file_pattern)
        if path.is_file():
            if path.resolve() not in exclude_paths:
                if path.suffix in args.extensions or not args.extensions:
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
    worker_args = [(file_path, args.batch_size) for file_path in files_to_process]
    if args.workers == 1:
        for w_args in worker_args:
            worker(w_args)
    else:
        with mp.Pool(processes=args.workers) as pool:
            pool.map(worker, worker_args)
    print("\n✓ All translations completed!")


if __name__ == "__main__":
    main()
