#!/data/data/com.termux/files/home/.local/bin/python


"""
A Linux dos2unix command implementation in Python.
Converts DOS/Windows line endings (CRLF) to Unix line endings (LF).

Features:
- Uses pathlib for cross-platform path handling
- Parallel processing for memory efficiency
- In-place file updates
- Accepts multiple files/folders as input
- Processes current directory recursively if no input is given
- Memory-optimized chunk-based reading/writing
- Automatically skips binary files and common directories
"""

from __future__ import annotations

import argparse
import logging
import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path

from dh import BIN_EXT, TXT_EXT

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
CHUNK_SIZE = 8192
BINARY_EXTENSIONS = BIN_EXT
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".coverage", ".egg-info", ".idea"}
TEXT_EXTENSIONS = TXT_EXT


def should_skip_dir(directory: Path) -> bool:
    return directory.name in SKIP_DIRS


def is_text_file(file_path: Path) -> bool:
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return False
    if file_path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    name_lower = file_path.name.lower()
    if name_lower in {"makefile", "dockerfile", "dockerfile.prod", "dockerfile.dev", "gemfile", "rakefile"}:
        return True
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            if not chunk:
                return True
            if b"\x00" in chunk:
                return False
            text_characters = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(32, 256)))
            return all(byte in text_characters for byte in chunk)
    except OSError:
        return False


def convert_dos_to_unix_chunk(chunk: bytes) -> bytes:
    return chunk.replace(b"\r\n", b"\n")


def convert_file(file_path: Path) -> tuple[str, bool, str]:
    try:
        if not file_path.is_file():
            return (str(file_path), False, "Not a file")
        if not is_text_file(file_path):
            return (str(file_path), False, "Binary file (skipped)")
        converted = False
        temp_data = bytearray()
        try:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    converted_chunk = convert_dos_to_unix_chunk(chunk)
                    if converted_chunk != chunk:
                        converted = True
                    temp_data.extend(converted_chunk)
            if converted:
                with open(file_path, "wb") as f:
                    f.write(temp_data)
                return (str(file_path), True, "Converted")
            else:
                return (str(file_path), True, "Already Unix format")
        except OSError as e:
            return (str(file_path), False, f"Read/Write error: {e}")
    except Exception as e:
        return (str(file_path), False, f"Error: {e}")


def find_text_files(paths: list[Path]) -> list[Path]:
    files = []
    for path in paths:
        if path.is_file():
            if is_text_file(path):
                files.append(path)
        elif path.is_dir():
            for text_file in path.rglob("*"):
                if any(should_skip_dir(parent) for parent in text_file.parents):
                    continue
                if text_file.is_file() and is_text_file(text_file):
                    files.append(text_file)
    return files


def get_input_paths(input_args: list[str] | None) -> list[Path]:
    if not input_args:
        return [Path.cwd()]
    paths = []
    for arg in input_args:
        path = Path(arg).resolve()
        if path.exists():
            paths.append(path)
        else:
            logger.warning(f"Path does not exist: {arg}")
    return paths


def main():
    parser = argparse.ArgumentParser(
        description="Convert DOS/Windows line endings (CRLF) to Unix (LF)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\nExamples:\n  %(prog)s file.txt\n  %(prog)s file1.txt file2.txt file3.txt\n  %(prog)s /path/to/folder\n  %(prog)s /path/to/folder file.txt\n  %(prog)s                    # Process current directory recursively\n\nSkip Directories: .git, __pycache__, .venv, venv, node_modules, .env, \n                  .pytest_cache, .tox, .mypy_cache, .coverage, dist, build\n        ",
    )
    parser.add_argument("paths", nargs="*", help="Files or folders to process (default: current directory)")
    parser.add_argument(
        "-j", "--jobs", type=int, default=cpu_count(), help=f"Number of parallel jobs (default: {cpu_count()})"
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output messages")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed output for each file")
    args = parser.parse_args()
    input_paths = get_input_paths(args.paths if args.paths else None)
    if not input_paths:
        logger.error("No valid paths provided")
        return 1
    files_to_process = find_text_files(input_paths)
    if not files_to_process:
        if not args.quiet:
            logger.info("No text files found to process")
        return 0
    if not args.quiet and (not args.verbose):
        logger.info(f"Processing {len(files_to_process)} file(s) with {args.jobs} worker(s)...")
    converted_count = 0
    skipped_count = 0
    error_count = 0
    try:
        with Pool(processes=args.jobs) as pool:
            results = pool.map(convert_file, files_to_process)
        for file_path, success, message in results:
            if args.verbose:
                status = "✓" if success else "✗"
                print(f"{status} {file_path}: {message}")
            if success:
                if "Converted" in message:
                    converted_count += 1
                else:
                    skipped_count += 1
            else:
                error_count += 1
        if not args.quiet:
            print()
            logger.info(f"Converted: {converted_count} file(s)")
            logger.info(f"Already Unix format: {skipped_count} file(s)")
            if error_count > 0:
                logger.warning(f"Errors: {error_count} file(s)")
        return 0 if error_count == 0 else 1
    except KeyboardInterrupt:
        logger.error("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
