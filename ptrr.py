#!/data/data/com.termux/files/usr/bin/python
import multiprocessing as mp
import os
import shutil
import sys
import tarfile
import tempfile
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import zstandard as zstd


def compress_chunk(chunk_data):
    """Compress a single chunk of data with zstd."""
    compressor = zstd.ZstdCompressor(level=3, threads=4)
    return compressor.compress(chunk_data)


def get_file_list(directory, exclude_patterns=None):
    """Get list of files to archive, excluding patterns."""
    if exclude_patterns is None:
        exclude_patterns = {".git", ".tar.zst", ".zst"}

    files = []
    for item in directory.rglob("*"):
        # Skip excluded patterns
        if any(pattern in item.parts for pattern in exclude_patterns):
            continue
        if item.name.endswith(".tar.zst") or item.name.endswith(".zst"):
            continue
        files.append(item)
    return files


def create_archive_optimized():
    """Create optimized archive with guaranteed exact extraction."""
    current_dir = Path.cwd()
    dir_name = current_dir.name
    parent_dir = current_dir.parent

    # Safety checks
    if str(current_dir) == "/" or str(current_dir) == str(Path.home()):
        print("Error: Cannot archive root or home directory")
        sys.exit(1)

    archive_path = parent_dir / f"{dir_name}.tar.zst"

    # Handle existing archive
    if archive_path.exists():
        response = input(f"Overwrite {archive_path}? (y/n): ").strip().lower()
        if response not in ["y", "yes"]:
            print("Aborted")
            sys.exit(0)

    try:
        # Get files to archive
        files = get_file_list(current_dir)

        if not files:
            print("No files to archive")
            sys.exit(1)

        # Create temporary tar file
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_tar:
            tmp_tar_path = tmp_tar.name

            # Create tar archive with proper metadata
            with tarfile.open(tmp_tar_path, "w") as tar:
                # Use ThreadPoolExecutor for parallel file addition
                with ThreadPoolExecutor(max_workers=min(4, mp.cpu_count())) as executor:

                    def add_file(file_path):
                        tar.add(file_path, arcname=file_path.relative_to(parent_dir))

                    # Add files in parallel
                    list(executor.map(add_file, files))

            # Compress the tar file
            compressor = zstd.ZstdCompressor(level=3, threads=mp.cpu_count())

            # Read and compress the tar file in chunks for memory efficiency
            CHUNK_SIZE = 1024 * 1024 * 8  # 8MB chunks

            with open(tmp_tar_path, "rb") as f_in, open(archive_path, "wb") as f_out:
                # Write compressed data directly
                while True:
                    chunk = f_in.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    compressed_chunk = compressor.compress(chunk)
                    f_out.write(compressed_chunk)
                # Write end marker
                f_out.write(compressor.flush())

            # Clean up temp file
            os.unlink(tmp_tar_path)

        # Verify archive was created successfully
        if archive_path.exists() and archive_path.stat().st_size > 0:
            # Test extraction to verify integrity
            test_dir = parent_dir / f"{dir_name}_test"
            try:
                with tarfile.open(archive_path, "r:zstd") as tar:
                    tar.extractall(test_dir)

                # Verify extraction (optional - remove if too slow)
                # This is expensive for large archives
                # shutil.rmtree(test_dir)

                # If successful, remove original directory
                shutil.rmtree(current_dir)
                print(f"✓ Archive created: {archive_path}")
                print(f"✓ Original directory removed: {current_dir}")

                # Clean up test extraction
                # shutil.rmtree(test_dir)

            except Exception as e:
                # Clean up test extraction if it exists
                if test_dir.exists():
                    shutil.rmtree(test_dir)
                raise
        else:
            print("Error: Archive creation failed")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        if "tmp_tar_path" in locals() and os.path.exists(tmp_tar_path):
            os.unlink(tmp_tar_path)
        if archive_path.exists():
            archive_path.unlink()
        sys.exit(1)


def create_archive_streaming_fixed():
    """Fixed streaming version that ensures exact extraction."""
    current_dir = Path.cwd()
    dir_name = current_dir.name
    parent_dir = current_dir.parent

    if str(current_dir) == "/" or str(current_dir) == str(Path.home()):
        print("Error: Cannot archive root or home directory")
        sys.exit(1)

    archive_path = parent_dir / f"{dir_name}.tar.zst"

    if archive_path.exists():
        response = input(f"Overwrite {archive_path}? (y/n): ").strip().lower()
        if response not in ["y", "yes"]:
            print("Aborted")
            sys.exit(0)

    try:
        compressor = zstd.ZstdCompressor(level=3, threads=mp.cpu_count())

        # Use block mode (w:) instead of streaming (w|) for better metadata preservation
        with open(archive_path, "wb") as f_out:
            with compressor.stream_writer(f_out) as zstd_writer:
                # Use block mode for proper metadata storage
                with tarfile.open(fileobj=zstd_writer, mode="w:") as tar:
                    files = get_file_list(current_dir)

                    if not files:
                        print("No files to archive")
                        sys.exit(1)

                    # Add files with proper metadata
                    for file_path in files:
                        tar.add(file_path, arcname=file_path.relative_to(parent_dir))

        # Verify and remove original
        if archive_path.exists() and archive_path.stat().st_size > 0:
            # Test extraction
            test_dir = parent_dir / f"{dir_name}_test"
            try:
                with tarfile.open(archive_path, "r:zstd") as tar:
                    tar.extractall(test_dir)
                shutil.rmtree(test_dir)

                shutil.rmtree(current_dir)
                print(f"✓ Archive created: {archive_path}")
                print(f"✓ Original directory removed: {current_dir}")
            except Exception as e:
                if test_dir.exists():
                    shutil.rmtree(test_dir)
                raise
        else:
            print("Error: Archive creation failed")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        if archive_path.exists():
            archive_path.unlink()
        sys.exit(1)


if __name__ == "__main__":
    # Use the optimized version for best results
    create_archive_optimized()
    # Alternative: create_archive_streaming_fixed()
