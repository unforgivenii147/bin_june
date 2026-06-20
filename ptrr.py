#!/data/data/com.termux/files/usr/bin/python

import json
import multiprocessing as mp
import os
import shutil
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import zstandard as zstd


def compress_file(args):
    """Compress a single file using zstd."""
    file_path, relative_path, level = args
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            compressor = zstd.ZstdCompressor(level=19, threads=6)
            compressed = compressor.compress(data)
            return (str(relative_path), compressed, len(data))
    except Exception as e:
        return (str(relative_path), None, 0)


def create_archive_with_parallel_compression():
    """Create archive by compressing each file in parallel."""

    current_dir = Path.cwd()
    dir_name = current_dir.name
    parent_dir = current_dir.parent

    if str(current_dir) == "/" or str(current_dir) == str(Path.home()):
        print("Error: Cannot run in root or home directory for safety!")
        sys.exit(1)

    archive_path = parent_dir / f"{dir_name}.tar.zst"

    if archive_path.exists():
        print(f"Warning: {archive_path} already exists!")

    print(f"Creating archive: {archive_path}")

    # Gather all files
    files = []
    for item in current_dir.rglob("*"):
        if item.is_file() and ".git" not in item.parts and not item.name.endswith(".tar.zst"):
            rel_path = item.relative_to(parent_dir)
            files.append((item, rel_path))

    print(f"Processing {len(files)} files in parallel...")

    # Prepare arguments for parallel compression
    args = [(str(f), str(r), 3) for f, r in files]

    # Compress files in parallel using all cores
    results = {}
    with ProcessPoolExecutor(max_workers=mp.cpu_count()) as executor:
        for file_path, compressed, original_size in executor.map(compress_file, args):
            if compressed:
                results[file_path] = (compressed, original_size)
                print(f"Compressed: {file_path} ({original_size} -> {len(compressed)} bytes)")
            else:
                print(f"Failed to compress: {file_path}")

    # Create a simple archive format (header + compressed data)
    # Format: [file_count][file1_path_length][file1_path][file1_compressed_size][file1_data]...
    archive_data = bytearray()

    # Write header
    archive_data.extend(len(results).to_bytes(4, "little"))

    for file_path, (compressed_data, original_size) in results.items():
        # Write path length
        path_bytes = file_path.encode("utf-8")
        archive_data.extend(len(path_bytes).to_bytes(4, "little"))
        # Write path
        archive_data.extend(path_bytes)
        # Write original size
        archive_data.extend(original_size.to_bytes(8, "little"))
        # Write compressed size
        archive_data.extend(len(compressed_data).to_bytes(8, "little"))
        # Write compressed data
        archive_data.extend(compressed_data)

    # Compress the entire archive (zstd will compress the combined data)
    compressor = zstd.ZstdCompressor(level=19, threads=6)
    final_compressed = compressor.compress(bytes(archive_data))

    # Write final archive
    with open(archive_path, "wb") as f:
        f.write(final_compressed)

    if archive_path.exists() and archive_path.stat().st_size > 0:
        print(f"Archive created! Size: {archive_path.stat().st_size / 1024:.2f} KB")
        print(f"Removing directory: {current_dir}")
        shutil.rmtree(current_dir)
        print("Done!")
    else:
        print("Error: Archive creation failed.")
        sys.exit(1)


if __name__ == "__main__":
    create_archive_with_parallel_compression()
