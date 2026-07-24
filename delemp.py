#!/data/data/com.termux/files/home/.local/bin/python

"""
Remove blank lines from files recursively using parallel processing.
Supports multiple input files/directories, optional space-only line removal,
and automatic binary file detection.
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator

# ANSI color codes
BOLD = "\x1b[1m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"
RED = "\x1b[31m"
RESET = "\x1b[0m"
DIM = "\x1b[2m"

# Extensions that are definitely text files
TEXT_EXTENSIONS = frozenset(
    {
        ".txt",
        ".py",
        ".pyw",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".less",
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
        ".cc",
        ".cxx",
        ".h",
        ".hpp",
        ".hxx",
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
        ".vue",
        ".svelte",
        ".astro",
        ".nix",
        ".hs",
        ".erl",
        ".ex",
        ".exs",
        ".clj",
        ".cljs",
        ".edn",
        ".dart",
        ".nim",
        ".zig",
        ".v",
        ".sv",
        ".asm",
        ".s",
        ".wat",
        ".wast",
        ".tf",
        ".tfvars",
        ".hcl",
        ".pkr",
    }
)

# Common binary file signatures
BINARY_SIGNATURES = (
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
    b"\x1f\x9d",
    b"\x1f\xa0",
    b"BZh",
    b"\xfd7zXZ\x00",
    b"7z\xbc\xaf'\x1c",
    b"Rar!\x1a\x07",
    b"\xed\xab\xee\xdb",
    b"\xd4\xc3\xb2\xa1",
    b"\xa1\xb2\xc3\xd4",
)

# Cache for text character validation
_TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(32, 127)) | set(range(128, 256)))
_BINARY_CHECK_SIZE = 8192


def is_binary_file(file_path: Path) -> bool:
    """Quickly determine if a file is binary using extension and content checks."""
    # Check extension first (fastest)
    if file_path.suffix.lower() in TEXT_EXTENSIONS:
        return False

    # Check for known binary extensions
    binary_extensions = {
        ".pyc",
        ".pyo",
        ".so",
        ".o",
        ".a",
        ".lib",
        ".dll",
        ".exe",
        ".bin",
        ".dat",
        ".db",
        ".sqlite",
        ".sqlite3",
    }
    if file_path.suffix.lower() in binary_extensions:
        return True

    # Read first chunk and check content
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(_BINARY_CHECK_SIZE)
    except OSError:
        return True

    if not chunk:
        return False

    # Check for null bytes (strongest binary indicator)
    if b"\x00" in chunk:
        return True

    # Check against known binary signatures
    for signature in BINARY_SIGNATURES:
        if chunk.startswith(signature):
            return True

    # Heuristic: count non-text characters
    non_text = sum(1 for byte in chunk if byte not in _TEXT_CHARS)
    if non_text / len(chunk) > 0.3:
        return True

    return False


def remove_blank_lines(file_path: Path, remove_spaces: bool = False) -> tuple[str, int, int, str]:
    """Remove blank lines from a file. Returns (path, total_lines, removed_lines, status)."""
    try:
        # Read file
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        total_lines = len(lines)

        # Filter lines based on mode
        if remove_spaces:
            new_lines = [line for line in lines if line.strip()]
        else:
            new_lines = [line for line in lines if line.strip("\n\r")]

        removed_lines = total_lines - len(new_lines)

        # Only write if changes were made
        if removed_lines > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

        return (str(file_path), total_lines, removed_lines, "processed")

    except UnicodeDecodeError:
        return (str(file_path), 0, 0, "binary")
    except Exception as e:
        return (str(file_path), 0, 0, f"error: {e}")


def process_file(args: tuple[Path, Path, bool]) -> tuple[str, int, int, str]:
    """Process a single file: check if binary, then remove blank lines."""
    base_dir, file_path, remove_spaces = args

    # Skip binary files early
    if is_binary_file(file_path):
        try:
            rel_path = file_path.relative_to(base_dir)
            return (str(rel_path), 0, 0, "binary")
        except ValueError:
            return (str(file_path), 0, 0, "binary")

    # Process text file
    result = remove_blank_lines(file_path, remove_spaces)

    # Convert to relative path for display
    try:
        rel_path = Path(result[0]).relative_to(base_dir)
        return (str(rel_path), result[1], result[2], result[3])
    except ValueError:
        return result


def collect_files(paths: list[Path]) -> list[tuple[Path, Path]]:
    """Collect all files from given paths (files and/or directories)."""
    files = []

    for path in paths:
        if not path.exists():
            print(f"{YELLOW}⚠ Warning:{RESET} '{path}' does not exist, skipping.")
            continue

        if path.is_file():
            # Single file: use its parent as base_dir
            if not path.is_symlink():
                files.append((path.parent, path))
        elif path.is_dir():
            # Directory: recursively collect files
            for file_path in path.rglob("*"):
                if file_path.is_file() and not file_path.is_symlink():
                    files.append((path, file_path))
        else:
            print(f"{YELLOW}⚠ Warning:{RESET} '{path}' is not a file or directory, skipping.")

    return files


def print_header(paths: list[Path], remove_spaces: bool):
    """Print the program header with processing information."""
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║{RESET}         {BOLD}Blank Line Remover{RESET}                    {BOLD}{CYAN}║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════╝{RESET}\n")

    print(f"{BOLD}Processing paths:{RESET}")
    for path in paths:
        path_type = "📄" if path.is_file() else "📁"
        print(f"  {path_type} {path.absolute()}")

    print(f"\n{BOLD}Mode:{RESET} ", end="")
    if remove_spaces:
        print(f"{YELLOW}Remove blank lines + whitespace-only lines{RESET}")
    else:
        print(f"{GREEN}Remove blank lines only{RESET}")
    print()


def print_results(results: list[tuple], total_removed: int, total_files: int, show_all_binary: bool = False):
    """Print detailed results of the processing."""
    print(f"\n{BOLD}{CYAN}{'─' * 70}{RESET}\n")

    # Sort results by path
    results.sort(key=lambda x: x[0])

    # Categorize results
    processed = [(p, t, r, s) for p, t, r, s in results if s == "processed"]
    skipped_binary = [(p, t, r, s) for p, t, r, s in results if s == "binary"]
    errors = [(p, t, r, s) for p, t, r, s in results if s not in ("processed", "binary")]

    # Print processed files
    if processed:
        print(f"{BOLD}{GREEN}✓ Modified files:{RESET}\n")
        for path, total_lines, removed, _ in processed:
            if removed > 0:
                print(f"  {GREEN}●{RESET} {path}")
                print(f"    {DIM}Lines: {total_lines:,}  →  Removed: {GREEN}{removed:,}{RESET}")
            else:
                print(f"  {DIM}○{RESET} {path} {DIM}(no blank lines found){RESET}")
        print()

    # Print skipped binary files
    if skipped_binary:
        print(f"{BOLD}{YELLOW}⊘ Skipped binary files: {len(skipped_binary)}{RESET}")
        display_count = len(skipped_binary) if show_all_binary else min(5, len(skipped_binary))
        for path, _, _, _ in skipped_binary[:display_count]:
            print(f"  {YELLOW}⊘{RESET} {path}")
        if len(skipped_binary) > display_count:
            print(f"  {DIM}... and {len(skipped_binary) - display_count} more binary files{RESET}")
        print()

    # Print errors
    if errors:
        print(f"{BOLD}{RED}✗ Errors:{RESET}\n")
        for path, _, _, status in errors:
            print(f"  {RED}✗{RESET} {path}")
            print(f"    {DIM}{status}{RESET}")
        print()

    # Print summary
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
        epilog="""
Examples:
  %(prog)s                          # Process current directory
  %(prog)s file.py                  # Process single file
  %(prog)s /path/to/dir             # Process single directory
  %(prog)s dir1 dir2 file.py        # Process multiple dirs and files
  %(prog)s -s .                     # Remove blank and whitespace-only lines
  %(prog)s -s dir1 file.py dir2     # Multiple targets with whitespace removal
  %(prog)s -w 8 /path/to/dir        # Use 8 worker processes
        """,
    )

    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files and/or directories to process (default: current directory)",
    )
    parser.add_argument(
        "-s",
        "--space",
        action="store_true",
        help="Also remove lines that contain only whitespace characters",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count)",
    )
    parser.add_argument(
        "--show-binary",
        action="store_true",
        help="Show all skipped binary files (default: shows only first 5)",
    )

    args = parser.parse_args()

    # Resolve all paths
    paths = [Path(p).resolve() for p in args.paths]

    # Print header
    print_header(paths, args.space)

    # Collect files
    print(f"{BOLD}Scanning for files...{RESET}", end=" ", flush=True)
    file_list = collect_files(paths)
    total_files = len(file_list)
    print(f"{GREEN}Done!{RESET} Found {BOLD}{total_files:,}{RESET} files.\n")

    if not file_list:
        print(f"{YELLOW}No files found to process.{RESET}")
        return

    # Prepare for processing
    process_args = [(base_dir, file_path, args.space) for base_dir, file_path in file_list]

    # Determine worker count
    max_workers = args.workers or min(32, (os.cpu_count() or 1) + 4)

    results = []
    total_removed = 0
    processed_count = 0
    skipped_count = 0
    error_count = 0

    print(f"{BOLD}Processing files...{RESET}")
    print(f"{DIM}(Using {max_workers} worker processes){RESET}\n")

    # Process files in parallel
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(process_file, arg): arg[1] for arg in process_args}

        completed = 0
        for future in as_completed(future_to_file):
            completed += 1
            try:
                result = future.result()
                _, _, removed, status = result

                total_removed += removed
                results.append(result)

                if status == "processed":
                    processed_count += 1
                elif status == "binary":
                    skipped_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                results.append((str(future_to_file[future]), 0, 0, f"error: {e}"))

            # Update progress
            binary_info = f" {YELLOW}({skipped_count} binary){RESET}" if skipped_count > 0 else ""
            error_info = f" {RED}({error_count} errors){RESET}" if error_count > 0 else ""
            print(
                f"\r  Progress: {completed:,}/{total_files:,} files processed{binary_info}{error_info}",
                end="",
                flush=True,
            )

    # Final progress update
    print(
        f"\r  Progress: {GREEN}Complete!{RESET} "
        f"{DIM}({processed_count:,} text, {skipped_count:,} binary, {error_count:,} errors){RESET}" + " " * 20
    )

    # Print results
    print_results(results, total_removed, total_files, args.show_binary)


if __name__ == "__main__":
    main()
