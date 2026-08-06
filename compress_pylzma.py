#!/data/data/com.termux/files/home/.local/bin/python
"""
Compress/decompress files recursively using pylzma with parallel processing.
"""

import argparse
import tarfile
import tempfile
import shutil
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import pylzma
import io


def create_tar_for_directory(dir_path):
    """Create a tar archive for a directory."""
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        tar.add(dir_path, arcname=dir_path.name)
    return tar_buffer.getvalue()


def compress_file(file_path, output_dir, tar_subdirs_first=False):
    """Compress a single file or directory using pylzma."""
    try:
        file_path = Path(file_path)
        if file_path.is_dir():
            if tar_subdirs_first:
                # Create tar archive first
                tar_data = create_tar_for_directory(file_path)
                compressed_data = pylzma.compress(tar_data)
                output_file = output_dir / f"{file_path.name}.tar.7z"
            else:
                # Compress each file in directory individually (this approach is simplified)
                # For directories without tar, we'll just skip them in this mode
                return None
        else:
            with open(file_path, "rb") as f:
                data = f.read()
            compressed_data = pylzma.compress(data)
            output_file = output_dir / f"{file_path.name}.7z"
        with open(output_file, "wb") as f:
            f.write(compressed_data)
        return f"Compressed: {file_path} -> {output_file}"
    except Exception as e:
        return f"Error compressing {file_path}: {str(e)}"


def decompress_file(file_path, output_dir):
    """Decompress a single file using pylzma."""
    try:
        file_path = Path(file_path)
        with open(file_path, "rb") as f:
            compressed_data = f.read()
        decompressed_data = pylzma.decompress(compressed_data)
        # Handle .tar.7z files
        if file_path.suffixes == [".tar", ".7z"]:
            # Extract tar archive
            output_name = file_path.name.replace(".tar.7z", "")
            tar_buffer = io.BytesIO(decompressed_data)
            with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                tar.extractall(path=output_dir)
            return f"Decompressed: {file_path} -> {output_dir}/{output_name}"
        # Handle regular .7z files
        elif file_path.suffix == ".7z":
            output_name = file_path.name.replace(".7z", "")
            output_file = output_dir / output_name
            with open(output_file, "wb") as f:
                f.write(decompressed_data)
            return f"Decompressed: {file_path} -> {output_file}"
        else:
            return f"Skipped (not a .7z or .tar.7z file): {file_path}"
    except Exception as e:
        return f"Error decompressing {file_path}: {str(e)}"


def process_files_parallel(files, output_dir, mode, tar_subdirs_first=False, max_workers=None):
    """Process files in parallel using ProcessPoolExecutor."""
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        if mode == "compress":
            futures = {executor.submit(compress_file, file, output_dir, tar_subdirs_first): file for file in files}
        else:  # decompress
            futures = {executor.submit(decompress_file, file, output_dir): file for file in files}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
                print(result)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Compress/decompress files recursively using pylzma with parallel processing"
    )
    parser.add_argument(
        "-c",
        "--compress",
        action="store_const",
        const="compress",
        dest="mode",
        default="compress",
        help="Compress files (default mode)",
    )
    parser.add_argument(
        "-d", "--decompress", action="store_const", const="decompress", dest="mode", help="Decompress files"
    )
    parser.add_argument(
        "-t",
        "--tar-subdirs-first",
        action="store_true",
        default=False,
        help="Tar subdirectories first before compression",
    )
    parser.add_argument(
        "-w", "--workers", type=int, default=None, help="Number of worker processes (default: CPU count)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="./compressed" if parser.parse_known_args()[0].mode != "decompress" else "./decompressed",
        help="Output directory (default: ./compressed for compress, ./decompressed for decompress)",
    )
    args = parser.parse_args()
    current_dir = Path(".")
    if args.mode == "compress":
        output_dir = Path(args.output or "./compressed")
        output_dir.mkdir(exist_ok=True)
        # Collect all files recursively (skip the output directory if it's inside current dir)
        all_files = []
        for item in current_dir.rglob("*"):
            if item.is_file() or (item.is_dir() and not args.tar_subdirs_first):
                # Skip files in output directory
                try:
                    if output_dir in item.parents or item == output_dir:
                        continue
                except (ValueError, AttributeError):
                    pass
                if item.is_file():
                    # Skip already compressed files
                    if item.suffix == ".7z":
                        continue
                    all_files.append(item)
                elif item.is_dir() and args.tar_subdirs_first:
                    # Add directories for tar+compress mode
                    if item != current_dir:  # Skip root directory
                        try:
                            if output_dir not in item.parents and item != output_dir:
                                all_files.append(item)
                        except (ValueError, AttributeError):
                            all_files.append(item)
        if not all_files:
            print("No files found to compress in current directory")
            return
        print(f"Found {len(all_files)} items to compress")
        print(f"Compressing to: {output_dir}")
        process_files_parallel(all_files, output_dir, "compress", args.tar_subdirs_first, args.workers)
    else:  # decompress
        output_dir = Path(args.output or "./decompressed")
        output_dir.mkdir(exist_ok=True)
        # Find all .7z and .tar.7z files
        compressed_files = []
        for item in current_dir.rglob("*"):
            if item.is_file() and (item.suffix == ".7z" or item.name.endswith(".tar.7z")):
                try:
                    if output_dir not in item.parents and item != output_dir:
                        compressed_files.append(item)
                except (ValueError, AttributeError):
                    compressed_files.append(item)
        if not compressed_files:
            print("No .7z or .tar.7z files found in current directory")
            return
        print(f"Found {len(compressed_files)} files to decompress")
        print(f"Decompressing to: {output_dir}")
        process_files_parallel(compressed_files, output_dir, "decompress", False, args.workers)


if __name__ == "__main__":
    main()
