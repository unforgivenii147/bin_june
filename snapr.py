#!/data/data/com.termux/files/home/.local/bin/python
"""
Snappy Compression/Decompression Tool
Recursively compresses/decompresses files using Snappy algorithm via cramjam
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing
import shutil
import sys
import tarfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import cramjam
except ImportError:
    print("Error: cramjam library required. Install with: pip install cramjam")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# File extensions
COMPRESSED_EXT = ".snappy"


def compress_file(file_path: Path, remove_original: bool = True) -> Tuple[bool, str]:
    """
    Compress a single file using Snappy

    Args:
        file_path: Path to file to compress
        remove_original: Whether to remove original file after compression

    Returns:
        Tuple of (success, message)
    """
    try:
        compressed_path = file_path.with_suffix(file_path.suffix + COMPRESSED_EXT)

        # Read original file
        with open(file_path, "rb") as f:
            data = f.read()

        # Compress using cramjam (snappy)
        compressed_data = cramjam.snappy.compress(data)

        # Write compressed file
        with open(compressed_path, "wb") as f:
            f.write(compressed_data)

        # Remove original if requested
        if remove_original:
            file_path.unlink()

        original_size = len(data)
        compressed_size = len(compressed_data)
        ratio = (compressed_size / original_size * 100) if original_size > 0 else 0

        logger.info(
            f"Compressed: {file_path} -> {compressed_path} ({original_size} -> {compressed_size} bytes, {ratio:.1f}%)"
        )

        return True, f"Compressed {file_path.name}"

    except Exception as e:
        logger.error(f"Error compressing {file_path}: {e!s}")
        return False, str(e)


def decompress_file(file_path: Path, remove_original: bool = True) -> Tuple[bool, str]:
    """
    Decompress a Snappy compressed file

    Args:
        file_path: Path to compressed file
        remove_original: Whether to remove compressed file after decompression

    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if file has .snappy extension
        if not file_path.suffix == COMPRESSED_EXT:
            return False, f"File {file_path} doesn't have {COMPRESSED_EXT} extension"

        # Determine output path (remove .snappy extension)
        original_suffix = file_path.suffixes[-2] if len(file_path.suffixes) > 1 else ""
        output_path = file_path.with_suffix("")

        # Read compressed file
        with open(file_path, "rb") as f:
            compressed_data = f.read()

        # Decompress using cramjam
        decompressed_data = cramjam.snappy.decompress(compressed_data)

        # Write decompressed file
        with open(output_path, "wb") as f:
            f.write(decompressed_data)

        # Remove original if requested
        if remove_original:
            file_path.unlink()

        logger.info(
            f"Decompressed: {file_path} -> {output_path} ({len(compressed_data)} -> {len(decompressed_data)} bytes)"
        )

        return True, f"Decompressed {file_path.name}"

    except Exception as e:
        logger.error(f"Error decompressing {file_path}: {e!s}")
        return False, str(e)


def process_file_worker(args):
    """
    Worker function for parallel processing
    """
    file_path, operation, remove_original = args

    if operation == "compress":
        return compress_file(file_path, remove_original)
    elif operation == "decompress":
        return decompress_file(file_path, remove_original)
    else:
        return False, f"Unknown operation: {operation}"


def find_files(directory: Path, operation: str, recursive: bool = True) -> List[Path]:
    """
    Find files to process based on operation

    Args:
        directory: Directory to search
        operation: 'compress' or 'decompress'
        recursive: Whether to search recursively

    Returns:
        List of file paths to process
    """
    files = []

    if operation == "compress":
        # Compress: find all files except those with .snappy extension
        for _ext in ["*"]:  # All files
            if recursive:
                pattern = "**/*"
            else:
                pattern = "*"

            for file_path in directory.glob(pattern):
                if file_path.is_file() and not file_path.suffix == COMPRESSED_EXT:
                    files.append(file_path)

    else:  # decompress
        # Decompress: find all .snappy files
        if recursive:
            pattern = f"**/*{COMPRESSED_EXT}"
        else:
            pattern = f"*{COMPRESSED_EXT}"

        for file_path in directory.glob(pattern):
            if file_path.is_file():
                files.append(file_path)

    return files


def create_tar_archive(directory: Path, remove_original: bool = True) -> Optional[Path]:
    """
    Create a tar archive of a directory

    Args:
        directory: Directory to archive
        remove_original: Whether to remove original directory after archiving

    Returns:
        Path to created tar file or None if failed
    """
    try:
        tar_path = directory.with_suffix(".tar")

        logger.info(f"Creating tar archive: {tar_path}")

        with tarfile.open(tar_path, "w") as tar:
            tar.add(directory, arcname=directory.name)

        if remove_original:
            shutil.rmtree(directory)
            logger.info(f"Removed original directory: {directory}")

        logger.info(f"Created tar archive: {tar_path}")
        return tar_path

    except Exception as e:
        logger.error(f"Error creating tar archive for {directory}: {e!s}")
        return None


def tar_subdirectories(base_dir: Path, remove_original: bool = True) -> List[Path]:
    """
    Tar all subdirectories in the base directory

    Args:
        base_dir: Base directory containing subdirectories to tar
        remove_original: Whether to remove original directories

    Returns:
        List of created tar file paths
    """
    tar_files = []

    for item in base_dir.iterdir():
        if item.is_dir():
            tar_path = create_tar_archive(item, remove_original)
            if tar_path:
                tar_files.append(tar_path)

    return tar_files


def process_files(
    file_paths: List[Path], operation: str, remove_original: bool = True, max_workers: Optional[int] = None
) -> Tuple[int, int]:
    """
    Process files in parallel

    Args:
        file_paths: List of file paths to process
        operation: 'compress' or 'decompress'
        remove_original: Whether to remove original files
        max_workers: Maximum number of worker processes

    Returns:
        Tuple of (success_count, failure_count)
    """
    if not file_paths:
        logger.warning(f"No files found to {operation}")
        return 0, 0

    if max_workers is None:
        max_workers = min(multiprocessing.cpu_count(), len(file_paths))

    logger.info(f"Processing {len(file_paths)} files with {max_workers} workers")

    success_count = 0
    failure_count = 0

    # Prepare arguments for workers
    args_list = [(fp, operation, remove_original) for fp in file_paths]

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_file_worker, args): args[0] for args in args_list}

        # Process results as they complete
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                success, message = future.result()
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                    logger.error(f"Failed to process {file_path}: {message}")
            except Exception as e:
                failure_count += 1
                logger.error(f"Error processing {file_path}: {e!s}")

    return success_count, failure_count


def main():
    parser = argparse.ArgumentParser(
        description="Compress or decompress files recursively using Snappy (cramjam)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compress all files in current directory recursively
  python snappy_tool.py -c .

  # Decompress all .snappy files in specific directory
  python snappy_tool.py -d /path/to/directory

  # Compress with tar of subdirectories first
  python snappy_tool.py -c -t .

  # Keep original files (don't remove)
  python snappy_tool.py -c --keep-original .
        """,
    )

    parser.add_argument("directory", type=str, help="Directory to process")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--compress", action="store_true", help="Compress files")
    group.add_argument("-d", "--decompress", action="store_true", help="Decompress files")

    parser.add_argument("-t", "--tar", action="store_true", help="Tar subdirectories first before compression")
    parser.add_argument("--keep-original", action="store_true", help="Keep original files (default: remove them)")
    parser.add_argument("--no-recursive", action="store_true", help="Do not process subdirectories recursively")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes (default: CPU count)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Validate directory
    base_dir = Path(args.directory)
    if not base_dir.exists() or not base_dir.is_dir():
        logger.error(f"Directory not found: {base_dir}")
        sys.exit(1)

    remove_original = not args.keep_original
    operation = "compress" if args.compress else "decompress"
    recursive = not args.no_recursive

    logger.info(f"Starting {operation} operation on {base_dir}")
    logger.info(f"Remove original: {remove_original}, Recursive: {recursive}")

    # Handle tar option for compression
    if args.tar and args.compress:
        logger.info("Tarring subdirectories...")
        tar_files = tar_subdirectories(base_dir, remove_original)
        logger.info(f"Created {len(tar_files)} tar archives")

        # Update base_dir to process tar files
        # The tar files are created in the same directory as the subdirectories
        # We'll continue with the base_dir for processing

    # Find files to process
    files_to_process = find_files(base_dir, operation, recursive)

    if not files_to_process:
        logger.warning(f"No files found to {operation}")
        sys.exit(0)

    logger.info(f"Found {len(files_to_process)} files to {operation}")

    # Process files
    success_count, failure_count = process_files(files_to_process, operation, remove_original, args.workers)

    # Summary
    logger.info(f"Completed {operation} operation")
    logger.info(f"Success: {success_count}, Failed: {failure_count}")

    if failure_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
