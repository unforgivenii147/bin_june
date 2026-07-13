#!/data/data/com.termux/files/usr/bin/env python


import argparse
import sys
from io import StringIO
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Tuple
from dh import TXT_EXT

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def process_file(file_path: Path) -> Tuple[str, int]:
    blank_lines_removed = 0
    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as infile:
            lines = infile.readlines()
        if not lines:
            return (str(file_path), 0)
        output_lines = []
        consecutive_blanks = 0
        for line in lines:
            is_blank = not line.strip()
            if is_blank:
                consecutive_blanks += 1
                if consecutive_blanks == 1:
                    output_lines.append("\n")
            else:
                if consecutive_blanks > 1:
                    blank_lines_removed += consecutive_blanks - 1
                consecutive_blanks = 0
                output_lines.append(line.rstrip("\n") + "\n")
        if consecutive_blanks > 1:
            blank_lines_removed += consecutive_blanks - 1
        if output_lines and lines and (not lines[-1].endswith("\n")):
            output_lines[-1] = output_lines[-1].rstrip("\n")
        temp_file = file_path.with_suffix(file_path.suffix + ".tmp")
        try:
            with temp_file.open("w", encoding="utf-8", errors="replace") as outfile:
                outfile.writelines(output_lines)
            temp_file.replace(file_path)
        except Exception:
            temp_file.unlink(missing_ok=True)
            raise
        print(f"Processed: {file_path} - Removed {blank_lines_removed} blank lines", file=sys.stderr)
        return (str(file_path), blank_lines_removed)
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}", file=sys.stderr)
        return (str(file_path), -1)


def collect_text_files(paths: List[str]) -> List[Path]:
    text_extensions = TXT_EXT
    files = []
    for path in paths:
        p = Path(path)
        if p.is_file() and p.suffix.lower() in text_extensions:
            files.append(p.resolve())
        elif p.is_dir():
            files.extend((f.resolve() for f in p.rglob("*") if f.is_file() and f.suffix.lower() in text_extensions))
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove extra blank lines from text files recursively.")
    parser.add_argument(
        "paths",
        metavar="PATH",
        nargs="*",
        default=["."],
        help="Files or directories to process (default: current directory)",
    )
    args = parser.parse_args()
    files = collect_text_files(args.paths)
    if not files:
        print("No text files found to process.", file=sys.stderr)
        return
    print(f"Found {len(files)} text file(s) to process.", file=sys.stderr)
    num_processes = max(1, cpu_count())
    with Pool(processes=num_processes) as pool:
        results = pool.map(process_file, files, chunksize=max(1, len(files) // (num_processes * 4)))
    valid_results = [(k, v) for k, v in results if v >= 0]
    valid_results.sort(key=lambda x: x[0])
    print("\nDetailed Results:")
    print("=" * 80)
    for file_path, blanks_removed in valid_results:
        if blanks_removed > 0:
            print(f"{file_path}: Removed {blanks_removed} blank lines")
        else:
            print(f"{file_path}: No extra blank lines found")
    total_blank_lines = sum((v for _, v in valid_results))
    failed_count = len(results) - len(valid_results)
    print("=" * 80)
    print(f"Files processed: {len(valid_results)}")
    print(f"Files failed: {failed_count}")
    print(f"Total blank lines removed: {total_blank_lines}")
    print("=" * 80)


if __name__ == "__main__":
    main()
