#!/data/data/com.termux/files/usr/bin/env python
"""
Parallel GZIP Compression Script
Compresses files recursively using maximum compression with gzip module.
Uses pathlib and parallel processing for efficiency.
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from typing import List, Tuple


class CompressionStats:
    """Track compression statistics."""

    def __init__(self):
        self.total_files = 0
        self.successful = 0
        self.failed = 0
        self.total_original_size = 0
        self.total_compressed_size = 0

    def add_success(self, original_size: int, compressed_size: int):
        self.total_files += 1
        self.successful += 1
        self.total_original_size += original_size
        self.total_compressed_size += compressed_size

    def add_failure(self):
        self.total_files += 1
        self.failed += 1


def compress_file(file_path: Path) -> Tuple[Path, bool, int, int, str]:
    """
    Compress a single file using gzip with maximum compression.

    Args:
        file_path: Path to the file to compress

    Returns:
        Tuple of (file_path, success, original_size, compressed_size, error_message)
    """
    gz_path = file_path.with_suffix(file_path.suffix + ".gz")

    try:
        # Get original file size
        original_size = file_path.stat().st_size

        # Compress with maximum compression (level 9)
        with open(file_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)

        # Get compressed file size
        compressed_size = gz_path.stat().st_size

        # Remove original file if compression successful
        file_path.unlink()

        return (file_path, True, original_size, compressed_size, "")

    except Exception as e:
        # Clean up partial gz file if it exists
        if gz_path.exists():
            gz_path.unlink()
        return (file_path, False, 0, 0, str(e))


def find_files_to_compress(directories: List[Path], skip_extensions: set = None) -> List[Path]:
    """
    Find all files recursively in given directories that should be compressed.

    Args:
        directories: List of directories to search
        skip_extensions: Set of extensions to skip (e.g., {'.gz', '.zip'})

    Returns:
        List of file paths to compress
    """
    if skip_extensions is None:
        skip_extensions = {".gz", ".zip", ".bz2", ".xz", ".7z", ".rar", ".tar"}

    files_to_compress = []

    for directory in directories:
        if not directory.exists():
            print(f"⚠ Warning: Directory '{directory}' does not exist, skipping...")
            continue

        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix not in skip_extensions:
                # Skip files that already have .gz extension
                if not file_path.suffix.endswith(".gz"):
                    files_to_compress.append(file_path)

    return files_to_compress


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_ratio(original: int, compressed: int) -> str:
    """Format compression ratio."""
    if original == 0:
        return "N/A"
    ratio = (1 - compressed / original) * 100
    return f"{ratio:.1f}%"


def main():
    parser = argparse.ArgumentParser(
        description="Compress files recursively with gzip (maximum compression)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Compress files in current directory
  %(prog)s dir1 dir2                 # Compress files in dir1 and dir2
  %(prog)s /path/to/dir1 /path/to/dir2  # Use absolute paths
  %(prog)s --workers 8 dir1          # Use 8 worker processes
        """,
    )

    parser.add_argument(
        "directories", nargs="*", default=["."], help="Directories to process (default: current directory)"
    )

    parser.add_argument(
        "--workers", "-w", type=int, default=None, help="Number of worker processes (default: CPU count)"
    )

    parser.add_argument(
        "--exclude", "-e", nargs="+", default=[], help="Additional file extensions to exclude (e.g., .pdf .jpg)"
    )

    args = parser.parse_args()

    # Convert directory strings to Path objects
    directories = [Path(d).resolve() for d in args.directories]

    print("\n" + "=" * 70)
    print("🔍 GZIP Compression Tool (Maximum Compression - Level 9)".center(70))
    print("=" * 70)
    print(f"\n📂 Processing directories:")
    for d in directories:
        print(f"   • {d}")

    # Setup skip extensions
    skip_extensions = {".gz", ".zip", ".bz2", ".xz", ".7z", ".rar", ".tar"}
    if args.exclude:
        for ext in args.exclude:
            if not ext.startswith("."):
                ext = "." + ext
            skip_extensions.add(ext)
        print(f"\n🚫 Excluding extensions: {', '.join(sorted(skip_extensions))}")

    # Find all files to compress
    print("\n🔎 Scanning for files...")
    start_time = time.time()
    files_to_compress = find_files_to_compress(directories, skip_extensions)

    if not files_to_compress:
        print("\n✅ No files found to compress!")
        return

    print(f"📊 Found {len(files_to_compress)} file(s) to compress\n")
    print("=" * 70)
    print(f"{'File':<50} {'Original':>10} {'Compressed':>10} {'Ratio':>8} {'Status':>10}")
    print("-" * 70)

    # Process files in parallel
    stats = CompressionStats()
    max_workers = args.workers

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all compression tasks
        future_to_file = {executor.submit(compress_file, file_path): file_path for file_path in files_to_compress}

        # Process completed tasks
        for future in as_completed(future_to_file):
            file_path, success, orig_size, comp_size, error = future.result()

            # Get relative path for display
            try:
                rel_path = file_path.relative_to(Path.cwd())
            except ValueError:
                rel_path = file_path

            # Display filename (truncate if too long)
            display_path = str(rel_path)
            if len(display_path) > 47:
                display_path = "..." + display_path[-44:]

            if success:
                stats.add_success(orig_size, comp_size)
                status_symbol = "✅"
                print(
                    f"{display_path:<50} {format_size(orig_size):>10} {format_size(comp_size):>10} {format_ratio(orig_size, comp_size):>8} {status_symbol:>10}"
                )
            else:
                stats.add_failure()
                status_symbol = "❌"
                print(f"{display_path:<50} {'N/A':>10} {'N/A':>10} {'N/A':>8} {status_symbol:>10}")
                if error:
                    print(f"   ⚠ Error: {error}")

    # Print summary
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 70)
    print("📊 COMPRESSION SUMMARY".center(70))
    print("=" * 70)
    print(f"  Total files processed:     {stats.total_files}")
    print(f"  Successfully compressed:   {stats.successful} ✅")
    print(f"  Failed compressions:       {stats.failed} ❌")
    print(f"  Original total size:       {format_size(stats.total_original_size)}")
    print(f"  Compressed total size:     {format_size(stats.total_compressed_size)}")
    if stats.total_original_size > 0:
        overall_ratio = (1 - stats.total_compressed_size / stats.total_original_size) * 100
        space_saved = stats.total_original_size - stats.total_compressed_size
        print(f"  Overall compression ratio: {overall_ratio:.1f}%")
        print(f"  Space saved:               {format_size(space_saved)}")
    print(f"  Time elapsed:               {timedelta(seconds=int(elapsed_time))}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
