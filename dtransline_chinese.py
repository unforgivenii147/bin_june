#!/data/data/com.termux/files/usr/bin/env python


"""
Translate Chinese lines in files to English in-place using parallel processing.
Specifically targets Chinese characters (CJK Unified Ideographs).
Requires: deep-translator
"""

import argparse
import multiprocessing as mp
import re
import sys
import time
from pathlib import Path
from typing import List, Tuple

try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("Please install deep-translator: pip install deep-translator")
    sys.exit(1)


def contains_chinese(text: str) -> bool:
    chinese_pattern = re.compile(r"[一-鿿㐀-䶿\u20000-⩭F⩰0-⭳F\u2b740-⮁F⮂0-⳪F豈-\ufaff⾀0-⾡F]")
    return bool(chinese_pattern.search(text))


def is_chinese_text(text: str, threshold: float = 0.3) -> bool:
    text = text.strip()
    if not text:
        return False
    total_chars = len([c for c in text if not c.isspace()])
    if total_chars == 0:
        return False
    chinese_chars = len(re.findall(r"[一-鿿㐀-䶿\u20000-⩭F⩰0-⭳F\u2b740-⮁F⮂0-⳪F豈-\ufaff⾀0-⾡F]", text))
    return chinese_chars / total_chars >= threshold


def translate_chinese_text(text: str, translator: GoogleTranslator, max_retries: int = 3) -> str:
    if not text.strip() or not contains_chinese(text):
        return text
    for attempt in range(max_retries):
        try:
            translated = translator.translate(text)
            print(translated)
            time.sleep(0.1)
            return translated
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 1.5
                print(f"  Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}", file=sys.stderr)
                time.sleep(wait_time)
            else:
                print(f"  Translation failed after {max_retries} attempts: {e}", file=sys.stderr)
                return text


def process_file(file_path: Path, dry_run: bool = False) -> dict:
    stats = {"file": str(file_path), "total_lines": 0, "chinese_lines": 0, "translated_lines": 0, "errors": 0}
    print(f"{('[DRY RUN] ' if dry_run else '')}Processing: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        stats["total_lines"] = len(lines)
        translator = None if dry_run else GoogleTranslator(source="auto", target="en")
        translated_lines = []
        chinese_found = False
        for i, line in enumerate(lines):
            if is_chinese_text(line):
                stats["chinese_lines"] += 1
                chinese_found = True
                if dry_run:
                    translated_lines.append(f"[CHINESE] {line}")
                else:
                    leading_ws = line[: len(line) - len(line.lstrip())]
                    trailing_ws = line[len(line.rstrip()) :]
                    stripped_line = line.strip()
                    translated_text = translate_chinese_text(stripped_line, translator)
                    translated_lines.append(leading_ws + translated_text + trailing_ws)
                    stats["translated_lines"] += 1
                    if stats["translated_lines"] % 10 == 0:
                        print(
                            f"  Progress: {stats['translated_lines']}/{stats['chinese_lines']} Chinese lines translated"
                        )
            else:
                translated_lines.append(line)
        if not dry_run and chinese_found:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(translated_lines)
            print(f"  ✓ Completed: {stats['translated_lines']} lines translated to English")
        elif dry_run and chinese_found:
            print(f"  ℹ Found {stats['chinese_lines']} lines with Chinese text (dry run)")
        else:
            print(f"  No Chinese text found, skipping.")
    except Exception as e:
        print(f"  ✗ Error processing {file_path}: {e}", file=sys.stderr)
        stats["errors"] += 1
    return stats


def worker(args: Tuple[Path, bool]) -> dict:
    file_path, dry_run = args
    return process_file(file_path, dry_run)


def collect_files(file_patterns: List[str], extensions: List[str], exclude_patterns: List[str]) -> List[Path]:
    files_to_process = []
    exclude_paths = [Path(p).resolve() for p in exclude_patterns]
    for file_pattern in file_patterns:
        path = Path(file_pattern)
        if not path.exists():
            print(f"Warning: {path} does not exist", file=sys.stderr)
            continue
        if path.is_file():
            if path.resolve() not in exclude_paths:
                if not extensions or path.suffix in extensions:
                    files_to_process.append(path)
        elif path.is_dir():
            for ext in extensions if extensions else ["*"]:
                pattern = f"*{ext}" if ext != "*" else "*"
                for file_path in path.rglob(pattern):
                    if file_path.is_file():
                        if file_path.resolve() in exclude_paths:
                            continue
                        if any((part.startswith(".") for part in file_path.parts)):
                            continue
                        if file_path.suffix in [".pyc", ".pyo", ".so", ".dll", ".exe", ".bin"]:
                            continue
                        files_to_process.append(file_path)
    seen = set()
    unique_files = []
    for f in files_to_process:
        if f.resolve() not in seen:
            seen.add(f.resolve())
            unique_files.append(f)
    return unique_files


def main():
    parser = argparse.ArgumentParser(
        description="Translate Chinese lines in files to English in-place",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\nExamples:\n  # Check for Chinese text in a file (dry run)\n  %(prog)s document.txt --dry-run\n  \n  # Translate Chinese text in multiple files\n  %(prog)s file1.txt file2.py file3.md\n  \n  # Translate all files in a directory\n  %(prog)s ./my_project/ --extensions .py .txt .md\n  \n  # Process with limited workers\n  %(prog)s ./docs/ --workers 2 --extensions .txt .md\n  \n  # Exclude certain directories\n  %(prog)s ./ --exclude ./node_modules ./venv ./.git\n        ",
    )
    parser.add_argument("files", nargs="+", type=str, help="Files or directories to process")
    parser.add_argument(
        "--extensions",
        "-e",
        nargs="+",
        default=[".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".csv"],
        help="File extensions to process (default: .txt .md .py .js .html .css .json .xml .csv)",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=mp.cpu_count(),
        help=f"Number of parallel workers (default: {mp.cpu_count()})",
    )
    parser.add_argument("--exclude", "-x", nargs="+", default=[], help="Files or directories to exclude")
    parser.add_argument(
        "--dry-run", "-d", action="store_true", help="Detect Chinese text without translating (no files modified)"
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.3,
        help="Minimum ratio of Chinese characters to consider a line as Chinese (default: 0.3)",
    )
    args = parser.parse_args()
    global is_chinese_text
    original_is_chinese_text = is_chinese_text

    def threshold_is_chinese_text(text: str) -> bool:
        return original_is_chinese_text(text, threshold=args.threshold)

    import inspect

    is_chinese_text = threshold_is_chinese_text
    files_to_process = collect_files(args.files, args.extensions, args.exclude)
    if not files_to_process:
        print("No files to process.")
        return
    print(f"Found {len(files_to_process)} files to process")
    if args.dry_run:
        print("DRY RUN MODE - No files will be modified")
    print(f"Using {args.workers} workers")
    print(f"Chinese detection threshold: {args.threshold:.0%}")
    print()
    worker_args = [(file_path, args.dry_run) for file_path in files_to_process]
    if args.workers == 1:
        all_stats = [worker(w_args) for w_args in worker_args]
    else:
        with mp.Pool(processes=args.workers) as pool:
            all_stats = pool.map(worker, worker_args)
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_files = len(all_stats)
    total_lines = sum((s["total_lines"] for s in all_stats))
    total_chinese_lines = sum((s["chinese_lines"] for s in all_stats))
    total_translated = sum((s["translated_lines"] for s in all_stats))
    total_errors = sum((s["errors"] for s in all_stats))
    print(f"Files processed: {total_files}")
    print(f"Total lines scanned: {total_lines:,}")
    print(f"Chinese lines found: {total_chinese_lines:,}")
    if not args.dry_run:
        print(f"Lines translated: {total_translated:,}")
    print(f"Errors encountered: {total_errors}")
    if total_chinese_lines > 0 and args.dry_run:
        print(f"\nℹ Run without --dry-run to translate {total_chinese_lines} Chinese lines")
    elif total_translated > 0:
        print(f"\n✓ Successfully translated {total_translated} Chinese lines to English")
    chinese_files = [s for s in all_stats if s["chinese_lines"] > 0]
    if chinese_files:
        print(f"\nFiles containing Chinese text:")
        for stats in chinese_files:
            print(f"  - {stats['file']}: {stats['chinese_lines']} Chinese lines")


if __name__ == "__main__":
    main()
