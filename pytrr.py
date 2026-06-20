#!/data/data/com.termux/files/usr/bin/python

import os
import shutil
import sys
import tarfile
import zstandard as zstd
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing as mp
import tempfile
import time


def compress_chunk(args):
    """Compress a chunk of data using zstd."""
    data, level = args
    compressor = zstd.ZstdCompressor(level=21, threads=6)
    return compressor.compress(data)


def create_archive_and_remove_multiprocessing():
    """Create archive with multiprocessing support."""

    current_dir = Path.cwd()
    dir_name = current_dir.name
    parent_dir = current_dir.parent

    # Safety check
    if str(current_dir) == "/" or str(current_dir) == str(Path.home()):
        print("Error: Cannot run in root or home directory for safety!")
        sys.exit(1)

    archive_path = parent_dir / f"{dir_name}.tar.zst"

    if archive_path.exists():
        print(f"Warning: {archive_path} already exists!")
        response = input("Overwrite? (y/n): ").strip().lower()
        if response not in ["y", "yes"]:
            print("Operation cancelled.")
            sys.exit(1)

    print(f"Creating archive: {archive_path}")

    try:
        # Option 1: Use zstd's built-in multi-threading (SIMPLEST)
        print("Using zstd built-in multi-threading...")
        compressor = zstd.ZstdCompressor(level=19, threads=6)

        # Create tar in memory
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_tar:
            tmp_tar_path = tmp_tar.name

            # Create tar with parallel file reading
            with tarfile.open(tmp_tar_path, "w") as tar:
                # Get all files
                files = []
                for item in current_dir.rglob("*"):
                    if ".git" in item.parts or item.name.endswith(".tar.zst"):
                        continue
                    files.append(item)

                print(f"Processing {len(files)} files...")

                # Use ThreadPoolExecutor for parallel file reading (I/O bound)
                with ThreadPoolExecutor(max_workers=min(8, mp.cpu_count())) as executor:
                    # Add files to tar (tar.add is I/O bound)
                    list(executor.map(lambda f: tar.add(f, arcname=f.relative_to(parent_dir)), files))

            # Read and compress with multi-threaded zstd
            with open(tmp_tar_path, "rb") as f_in:
                data = f_in.read()
                compressed_data = compressor.compress(data)

            # Write compressed data
            with open(archive_path, "wb") as f_out:
                f_out.write(compressed_data)

            os.unlink(tmp_tar_path)

        # Verify
        if archive_path.exists() and archive_path.stat().st_size > 0:
            print(f"Archive created! Size: {archive_path.stat().st_size / 1024:.2f} KB")
            print(f"Removing directory: {current_dir}")
            shutil.rmtree(current_dir)
            print("Done!")
        else:
            print("Error: Archive creation failed.")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        if "tmp_tar_path" in locals() and os.path.exists(tmp_tar_path):
            os.unlink(tmp_tar_path)
        sys.exit(1)


def create_archive_streaming_multithreaded():
    """Streaming version with multithreaded compression."""

    current_dir = Path.cwd()
    dir_name = current_dir.name
    parent_dir = current_dir.parent

    if str(current_dir) == "/" or str(current_dir) == str(Path.home()):
        print("Error: Cannot run in root or home directory for safety!")
        sys.exit(1)

    archive_path = parent_dir / f"{dir_name}.tar.zst"

    if archive_path.exists():
        print(f"Warning: {archive_path} already exists!")
        response = input("Overwrite? (y/n): ").strip().lower()
        if response not in ["y", "yes"]:
            print("Operation cancelled.")
            sys.exit(1)

    print(f"Creating archive: {archive_path}")
    print(f"Using {mp.cpu_count()} threads for compression")

    try:
        # Multithreaded zstd compressor
        compressor = zstd.ZstdCompressor(
            level=19,
            threads=6,  # Use all cores
            # Optional: tune for speed
            target_length=4096,
            overlap_log=9,
        )

        with open(archive_path, "wb") as f_out:
            with compressor.stream_writer(f_out) as zstd_writer:
                # Create tar in streaming mode
                with tarfile.open(fileobj=zstd_writer, mode="w|") as tar:
                    # Get all files
                    files = []
                    for item in current_dir.rglob("*"):
                        if ".git" in item.parts or item.name.endswith(".tar.zst"):
                            continue
                        files.append(item)

                    print(f"Processing {len(files)} files...")

                    # Sequential tar creation (tarfile doesn't support parallel adding)
                    # But the compression happens in parallel via zstd's threads
                    for file_path in files:
                        tar.add(file_path, arcname=file_path.relative_to(parent_dir))

        if archive_path.exists() and archive_path.stat().st_size > 0:
            print(f"Archive created! Size: {archive_path.stat().st_size / 1024:.2f} KB")
            print(f"Removing directory: {current_dir}")
            shutil.rmtree(current_dir)
            print("Done!")
        else:
            print("Error: Archive creation failed.")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import time

    start = time.time()

    # Choose one:
    # create_archive_and_remove_multiprocessing()  # In-memory with parallel reading
    create_archive_streaming_multithreaded()  # Streaming with multithreaded compression

    print(f"Time: {time.time() - start:.2f} seconds")
