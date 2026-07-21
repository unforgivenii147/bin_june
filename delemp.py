#!/data/data/com.termux/files/usr/bin/env python


"""
Remove blank lines from files recursively using parallel processing.
Supports multiple input directories, optional space-only line removal,
and automatic binary file detection.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import list, tuple

BOLD = "\x1b[1m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"
RED = "\x1b[31m"
RESET = "\x1b[0m"
DIM = "\x1b[2m"
TEXT_EXTENSIONS = {
    ".txt",
    ".py",
    ".js",
    ".html",
    ".css",
    ".json",
    ".xml",
    ".md",
    ".rst",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".log",
    ".csv",
    ".tsv",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".java",
    ".kt",
    ".scala",
    ".rs",
    ".go",
    ".rb",
    ".php",
    ".pl",
    ".pm",
    ".lua",
    ".r",
    ".m",
    ".swift",
    ".ts",
    ".jsx",
    ".tsx",
    ".vue",
    ".svelte",
    ".sql",
    ".graphql",
    ".proto",
    ".tex",
    ".bib",
    ".make",
    ".cmake",
    ".dockerfile",
    ".gitignore",
    ".env",
    ".editorconfig",
    ".eslintrc",
    ".prettierrc",
    ".babelrc",
}
BINARY_SIGNATURES = [
    b"\x00",
    b"\xff\xd8\xff",
    b"\x89PNG",
    b"GIF8",
    b"BM",
    b"\x00\x00\x01\x00",
    b"PK\x03\x04",
    b"\x1f\x8b",
    b"\x7fELF",
    b"MZ",
    b"\xca\xfe\xba\xbe",
    b"%PDF",
    b"\xd0\xcf\x11\xe0",
    b"SQLite format 3",
    b"RIFF",
    b"\x1aE\xdf\xa3",
    b"\x00\x00\x00\x18ftyp",
    b"\x00\x00\x00\x1cftyp",
    b"ID3",
    b"OggS",
    b"fLaC",
    b"FWS",
    b"CWS",
    b"%!PS",
    b"%!PS",
    b"\x1f\x9d",
    b"\x1f\xa0",
    b"BZh",
    b"\xfd7zXZ\x00",
    b"7z\xbc\xaf'\x1c",
    b"Rar!\x1a\x07",
    b"\xed\xab\xee\xdb",
    b"\xd4\xc3\xb2\xa1",
    b"\xa1\xb2\xc3\xd4",
]


def is_binary_file(file_path: Path) -> bool:
    suffix = file_path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return False
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        for signature in BINARY_SIGNATURES:
            if chunk.startswith(signature):
                return True
        text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(32, 127)) | set(range(128, 256)))
        if chunk:
            non_text = sum(1 for byte in chunk if byte not in text_chars)
            non_text_ratio = non_text / len(chunk)
            if non_text_ratio > 0.3:
                return True
        return False
    except OSError:
        return True


def remove_blank_lines(file_path: Path, remove_spaces: bool = False) -> tuple[str, int, int, str]:
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        total_lines = len(lines)
        if remove_spaces:
            new_lines = [line for line in lines if line.strip()]
        else:
            new_lines = [line for line in lines if line.strip("\n\r")]
        removed_lines = total_lines - len(new_lines)
        if removed_lines > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        return (str(file_path), total_lines, removed_lines, "processed")
    except UnicodeDecodeError:
        return (str(file_path), 0, 0, "binary")
    except Exception as e:
        return (str(file_path), 0, 0, f"error: {e!s}")


def process_file(args: tuple[Path, Path, bool]) -> tuple[str, int, int, str]:
    base_dir, file_path, remove_spaces = args
    if is_binary_file(file_path):
        try:
            rel_path = file_path.relative_to(base_dir)
            return (str(rel_path), 0, 0, "binary")
        except ValueError:
            return (str(file_path), 0, 0, "binary")
    result = remove_blank_lines(file_path, remove_spaces)
    if isinstance(result, tuple) and len(result) == 4:
        abs_path, total, removed, status = result
        try:
            rel_path = Path(abs_path).relative_to(base_dir)
            return (str(rel_path), total, removed, status)
        except ValueError:
            return result
    return result


def collect_files(directories: list[Path]) -> list[tuple[Path, Path]]:
    files = []
    for directory in directories:
        if not directory.exists():
            print(f"{YELLOW}⚠ Warning:{RESET} Directory '{directory}' does not exist, skipping.")
            continue
        if not directory.is_dir():
            print(f"{YELLOW}⚠ Warning:{RESET} '{directory}' is not a directory, skipping.")
            continue
        for file_path in directory.rglob("*"):
            if file_path.is_file() and (not file_path.is_symlink()):
                files.append((directory, file_path))
    return files


def print_header(directories: list[Path], remove_spaces: bool):
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║{RESET}         {BOLD}Blank Line Remover{RESET}                    {BOLD}{CYAN}║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════╝{RESET}\n")
    print(f"{BOLD}Processing directories:{RESET}")
    for directory in directories:
        print(f"  • {directory.absolute()}")
    print(f"\n{BOLD}Mode:{RESET} ", end="")
    if remove_spaces:
        print(f"{YELLOW}Remove blank lines + whitespace-only lines{RESET}")
    else:
        print(f"{GREEN}Remove blank lines only{RESET}")
    print()


def print_results(results: list[tuple], total_removed: int, total_files: int):
    print(f"\n{BOLD}{CYAN}{'─' * 70}{RESET}\n")
    results.sort(key=lambda x: x[0])
    processed = []
    skipped_binary = []
    errors = []
    for result in results:
        path, total_lines, removed, status = result
        if status == "processed":
            processed.append(result)
        elif status == "binary":
            skipped_binary.append(result)
        else:
            errors.append(result)
    if processed:
        print(f"{BOLD}{GREEN}✓ Modified files:{RESET}\n")
        for path, total_lines, removed, status in processed:
            if removed > 0:
                print(f"  {GREEN}●{RESET} {path}")
                print(f"    {DIM}Lines: {total_lines:,}  →  Removed: {GREEN}{removed:,}{RESET}")
            else:
                print(f"  {DIM}○{RESET} {path} {DIM}(no blank lines found){RESET}")
        print()
    if skipped_binary:
        print(f"{BOLD}{YELLOW}⊘ Skipped binary files: {len(skipped_binary)}{RESET}")
        for path, _, _, _ in skipped_binary[:5]:
            print(f"  {YELLOW}⊘{RESET} {path}")
        if len(skipped_binary) > 5:
            print(f"  {DIM}... and {len(skipped_binary) - 5} more binary files{RESET}")
        print()
    if errors:
        print(f"{BOLD}{RED}✗ Errors:{RESET}\n")
        for path, _, _, status in errors:
            print(f"  {RED}✗{RESET} {path}")
            print(f"    {DIM}{status}{RESET}")
        print()
    print(f"{BOLD}{CYAN}{'─' * 70}{RESET}")
    print(f"{BOLD}Summary:{RESET}")
    print(f"  Total files found:     {BOLD}{total_files:,}{RESET}")
    print(f"  Text files processed:  {BOLD}{len(processed):,}{RESET}")
    print(f"  Binary files skipped:  {BOLD}{YELLOW}{len(skipped_binary):,}{RESET}")
    print(f"  Files modified:        {BOLD}{sum(1 for r in processed if r[2] > 0):,}{RESET}")
    print(f"  Lines removed:         {BOLD}{GREEN}{total_removed:,}{RESET}")
    if errors:
        print(f"  Errors:                {BOLD}{RED}{len(errors):,}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 70}{RESET}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Remove blank lines from files recursively using parallel processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\nExamples:\n  %(prog)s                          # Process current directory\n  %(prog)s /path/to/dir             # Process single directory\n  %(prog)s dir1 dir2 dir3           # Process multiple directories\n  %(prog)s -s .                     # Remove blank and whitespace-only lines\n  %(prog)s -s dir1 dir2             # Multiple dirs with whitespace removal\n  %(prog)s -w 8 /path/to/dir        # Use 8 worker processes\n        ",
    )
    parser.add_argument(
        "directories", nargs="*", default=["."], help="Directories to process (default: current directory)"
    )
    parser.add_argument(
        "-s", "--space", action="store_true", help="Also remove lines that contain only whitespace characters"
    )
    parser.add_argument(
        "-w", "--workers", type=int, default=None, help="Number of worker processes (default: CPU count)"
    )
    parser.add_argument(
        "--show-binary", action="store_true", help="Show all skipped binary files (default: shows only first 5)"
    )
    args = parser.parse_args()
    directories = [Path(d).resolve() for d in args.directories]
    print_header(directories, args.space)
    print(f"{BOLD}Scanning for files...{RESET}", end=" ")
    file_list = collect_files(directories)
    print(f"{GREEN}Done!{RESET} Found {BOLD}{len(file_list):,}{RESET} files.\n")
    if not file_list:
        print(f"{YELLOW}No files found to process.{RESET}")
        return
    process_args = [(base_dir, file_path, args.space) for base_dir, file_path in file_list]
    results = []
    total_removed = 0
    processed_count = 0
    skipped_count = 0
    print(f"{BOLD}Processing files...{RESET}")
    print(f"{DIM}(Using {args.workers or 'default'} worker processes){RESET}\n")
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_to_file = {executor.submit(process_file, arg): arg[1] for arg in process_args}
        completed = 0
        for future in as_completed(future_to_file):
            completed += 1
            result = future.result()
            if len(result) == 4:
                _, _, removed, status = result
                total_removed += removed
                results.append(result)
                if status == "binary":
                    skipped_count += 1
                elif status == "processed":
                    processed_count += 1
            binary_indicator = f" {YELLOW}({skipped_count} binary skipped){RESET}" if skipped_count > 0 else ""
            print(f"\r  Progress: {completed:,}/{len(file_list):,} files processed{binary_indicator}", end="")
    print(
        f"\r  Progress: {GREEN}Complete!{RESET} {DIM}({processed_count:,} text, {skipped_count:,} binary){RESET}"
        + " " * 20
    )
    print_results(results, total_removed, len(file_list))


if __name__ == "__main__":
    main()
