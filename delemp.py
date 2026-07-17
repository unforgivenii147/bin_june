#!/data/data/com.termux/files/usr/bin/env python
"""
Remove blank lines from files recursively using parallel processing.
Supports multiple input directories, optional space-only line removal,
and automatic binary file detection.
"""

import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple

# Rich formatting
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
RESET = "\033[0m"
DIM = "\033[2m"

# Common text file extensions
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

# Binary file signatures (magic bytes)
BINARY_SIGNATURES = [
    b"\x00",  # Null byte (common in binary files)
    b"\xff\xd8\xff",  # JPEG
    b"\x89PNG",  # PNG
    b"GIF8",  # GIF
    b"BM",  # BMP
    b"\x00\x00\x01\x00",  # ICO
    b"PK\x03\x04",  # ZIP, DOCX, etc.
    b"\x1f\x8b",  # GZIP
    b"\x7fELF",  # ELF (Linux executables)
    b"MZ",  # PE (Windows executables)
    b"\xca\xfe\xba\xbe",  # Mach-O (macOS executables)
    b"%PDF",  # PDF
    b"\xd0\xcf\x11\xe0",  # MS Office (older formats)
    b"SQLite format 3",  # SQLite
    b"RIFF",  # WAV, AVI
    b"\x1a\x45\xdf\xa3",  # WebM/MKV
    b"\x00\x00\x00\x18ftyp",  # MP4
    b"\x00\x00\x00\x1cftyp",  # MP4
    b"ID3",  # MP3
    b"OggS",  # OGG
    b"\x66\x4c\x61\x43",  # FLAC
    b"FWS",  # SWF
    b"CWS",  # SWF compressed
    b"%!PS",  # PostScript
    b"\x25\x21\x50\x53",  # EPS
    b"\x1f\x9d",  # Compressed (LZW)
    b"\x1f\xa0",  # Compressed (LZH)
    b"BZh",  # BZIP2
    b"\xfd7zXZ\x00",  # XZ
    b"7z\xbc\xaf\x27\x1c",  # 7-Zip
    b"Rar!\x1a\x07",  # RAR
    b"\xed\xab\xee\xdb",  # RPM
    b"\xd4\xc3\xb2\xa1",  # PCAP
    b"\xa1\xb2\xc3\xd4",  # PCAP (swapped)
]


def is_binary_file(file_path: Path) -> bool:
    """
    Detect if a file is binary using multiple methods:
    1. Check file extension against known text extensions
    2. Check for null bytes (most reliable binary indicator)
    3. Check for binary file signatures (magic bytes)

    Args:
        file_path: Path to the file

    Returns:
        True if file appears to be binary, False otherwise
    """
    # Method 1: Check extension
    suffix = file_path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return False

    # If no extension or unknown extension, check content
    try:
        # Read first 8KB of the file for analysis
        with open(file_path, "rb") as f:
            chunk = f.read(8192)

        if not chunk:
            return False  # Empty files are treated as text

        # Method 2: Check for null bytes (most reliable binary indicator)
        if b"\x00" in chunk:
            return True

        # Method 3: Check for binary file signatures
        for signature in BINARY_SIGNATURES:
            if chunk.startswith(signature):
                return True

        # Method 4: Heuristic - check if high percentage of non-printable characters
        # Count control characters (excluding common whitespace)
        text_chars = bytearray(
            {7, 8, 9, 10, 12, 13, 27}  # Common control chars
            | set(range(0x20, 0x7F))  # Printable ASCII
            | set(range(0x80, 0x100))  # Extended ASCII (UTF-8 continuation)
        )

        if chunk:
            non_text = sum(1 for byte in chunk if byte not in text_chars)
            non_text_ratio = non_text / len(chunk)

            # If more than 30% non-text characters, consider it binary
            if non_text_ratio > 0.3:
                return True

        return False

    except (IOError, OSError):
        # If we can't read the file, skip it
        return True


def remove_blank_lines(file_path: Path, remove_spaces: bool = False) -> Tuple[str, int, int, str]:
    """
    Process a single file: remove blank lines (and optionally space-only lines).

    Args:
        file_path: Path to the file to process
        remove_spaces: If True, also remove lines containing only whitespace

    Returns:
        Tuple of (relative_path_str, total_lines, removed_lines, status)
    """
    try:
        # Read all lines
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        total_lines = len(lines)

        # Filter out blank lines (and optionally whitespace-only lines)
        if remove_spaces:
            # Keep lines that are not empty and not whitespace-only
            new_lines = [line for line in lines if line.strip()]
        else:
            # Keep lines that are not just a newline
            new_lines = [line for line in lines if line.strip("\n\r")]

        removed_lines = total_lines - len(new_lines)

        # Only write if lines were actually removed
        if removed_lines > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

        return (str(file_path), total_lines, removed_lines, "processed")

    except UnicodeDecodeError:
        return (str(file_path), 0, 0, "binary")
    except Exception as e:
        return (str(file_path), 0, 0, f"error: {str(e)}")


def process_file(args: Tuple[Path, Path, bool]) -> Tuple[str, int, int, str]:
    """
    Wrapper for parallel processing.

    Args:
        args: Tuple of (base_dir, file_path, remove_spaces)

    Returns:
        Processing result tuple
    """
    base_dir, file_path, remove_spaces = args

    # Check if file is binary before processing
    if is_binary_file(file_path):
        try:
            rel_path = file_path.relative_to(base_dir)
            return (str(rel_path), 0, 0, "binary")
        except ValueError:
            return (str(file_path), 0, 0, "binary")

    result = remove_blank_lines(file_path, remove_spaces)

    # Convert absolute path to relative
    if isinstance(result, tuple) and len(result) == 4:
        abs_path, total, removed, status = result
        try:
            rel_path = Path(abs_path).relative_to(base_dir)
            return (str(rel_path), total, removed, status)
        except ValueError:
            return result

    return result


def collect_files(directories: List[Path]) -> List[Tuple[Path, Path]]:
    """
    Collect all regular files from given directories recursively.

    Args:
        directories: List of base directories

    Returns:
        List of (base_dir, file_path) tuples
    """
    files = []
    for directory in directories:
        if not directory.exists():
            print(f"{YELLOW}⚠ Warning:{RESET} Directory '{directory}' does not exist, skipping.")
            continue
        if not directory.is_dir():
            print(f"{YELLOW}⚠ Warning:{RESET} '{directory}' is not a directory, skipping.")
            continue

        for file_path in directory.rglob("*"):
            if file_path.is_file() and not file_path.is_symlink():
                files.append((directory, file_path))

    return files


def print_header(directories: List[Path], remove_spaces: bool):
    """Print a formatted header with processing information."""
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


def print_results(results: List[Tuple], total_removed: int, total_files: int):
    """Print formatted results."""
    print(f"\n{BOLD}{CYAN}{'─' * 70}{RESET}\n")

    # Sort results by path for consistent output
    results.sort(key=lambda x: x[0])

    # Categorize results
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

    # Print processed files
    if processed:
        print(f"{BOLD}{GREEN}✓ Modified files:{RESET}\n")
        for path, total_lines, removed, status in processed:
            if removed > 0:
                print(f"  {GREEN}●{RESET} {path}")
                print(f"    {DIM}Lines: {total_lines:,}  →  Removed: {GREEN}{removed:,}{RESET}")
            else:
                print(f"  {DIM}○{RESET} {path} {DIM}(no blank lines found){RESET}")
        print()

    # Print skipped binary files (collapsed by default)
    if skipped_binary:
        print(f"{BOLD}{YELLOW}⊘ Skipped binary files: {len(skipped_binary)}{RESET}")
        # Show first 5 binary files as examples
        for path, _, _, _ in skipped_binary[:5]:
            print(f"  {YELLOW}⊘{RESET} {path}")
        if len(skipped_binary) > 5:
            print(f"  {DIM}... and {len(skipped_binary) - 5} more binary files{RESET}")
        print()

    # Print errors
    if errors:
        print(f"{BOLD}{RED}✗ Errors:{RESET}\n")
        for path, _, _, status in errors:
            print(f"  {RED}✗{RESET} {path}")
            print(f"    {DIM}{status}{RESET}")
        print()

    # Summary
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
  %(prog)s /path/to/dir             # Process single directory
  %(prog)s dir1 dir2 dir3           # Process multiple directories
  %(prog)s -s .                     # Remove blank and whitespace-only lines
  %(prog)s -s dir1 dir2             # Multiple dirs with whitespace removal
  %(prog)s -w 8 /path/to/dir        # Use 8 worker processes
        """,
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

    # Convert directory strings to Path objects
    directories = [Path(d).resolve() for d in args.directories]

    # Print header
    print_header(directories, args.space)

    # Collect all files
    print(f"{BOLD}Scanning for files...{RESET}", end=" ")
    file_list = collect_files(directories)
    print(f"{GREEN}Done!{RESET} Found {BOLD}{len(file_list):,}{RESET} files.\n")

    if not file_list:
        print(f"{YELLOW}No files found to process.{RESET}")
        return

    # Prepare arguments for parallel processing
    process_args = [(base_dir, file_path, args.space) for base_dir, file_path in file_list]

    # Process files in parallel
    results = []
    total_removed = 0
    processed_count = 0
    skipped_count = 0

    print(f"{BOLD}Processing files...{RESET}")
    print(f"{DIM}(Using {args.workers or 'default'} worker processes){RESET}\n")

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_file, arg): arg[1] for arg in process_args}

        # Process completed tasks with progress indication
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

            # Show progress with counts
            binary_indicator = f" {YELLOW}({skipped_count} binary skipped){RESET}" if skipped_count > 0 else ""
            print(f"\r  Progress: {completed:,}/{len(file_list):,} files processed{binary_indicator}", end="")

    print(
        f"\r  Progress: {GREEN}Complete!{RESET} {DIM}({processed_count:,} text, {skipped_count:,} binary){RESET}"
        + " " * 20
    )

    # Print detailed results
    print_results(results, total_removed, len(file_list))


if __name__ == "__main__":
    main()
