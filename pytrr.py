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
    data, level = args
    compressor = zstd.ZstdCompressor(level=3, threads=4)
    return compressor.compress(data)


def create_archive_and_remove_multiprocessing():
    current_dir = Path.cwd()
    dir_name = current_dir.name
    parent_dir = current_dir.parent
    if str(current_dir) == "/" or str(current_dir) == str(Path.home()):
        sys.exit(1)
    archive_path = parent_dir / f"{dir_name}.tar.zst"
    if archive_path.exists():
        response = input("Overwrite? (y/n): ").strip().lower()
        if response not in ["y", "yes"]:
            sys.exit(1)
    try:
        compressor = zstd.ZstdCompressor(level=3, threads=4)
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_tar:
            tmp_tar_path = tmp_tar.name
            with tarfile.open(tmp_tar_path, "w") as tar:
                files = []
                for item in current_dir.rglob("*"):
                    if ".git" in item.parts or item.name.endswith(".tar.zst"):
                        continue
                    files.append(item)
                with ThreadPoolExecutor(max_workers=min(8, mp.cpu_count())) as executor:
                    list(executor.map(lambda f: tar.add(f, arcname=f.relative_to(parent_dir)), files))
            with open(tmp_tar_path, "rb") as f_in:
                data = f_in.read()
                compressed_data = compressor.compress(data)
            with open(archive_path, "wb") as f_out:
                f_out.write(compressed_data)
            os.unlink(tmp_tar_path)
        if archive_path.exists() and archive_path.stat().st_size > 0:
            shutil.rmtree(current_dir)
        else:
            sys.exit(1)
    except Exception as e:
        if "tmp_tar_path" in locals() and os.path.exists(tmp_tar_path):
            os.unlink(tmp_tar_path)
        sys.exit(1)


def create_archive_streaming_multithreaded():
    current_dir = Path.cwd()
    dir_name = current_dir.name
    parent_dir = current_dir.parent
    if str(current_dir) == "/" or str(current_dir) == str(Path.home()):
        sys.exit(1)
    archive_path = parent_dir / f"{dir_name}.tar.zst"
    if archive_path.exists():
        response = input("Overwrite? (y/n): ").strip().lower()
        if response not in ["y", "yes"]:
            sys.exit(1)
    try:
        compressor = zstd.ZstdCompressor(level=3, threads=4)
        with open(archive_path, "wb") as f_out:
            with compressor.stream_writer(f_out) as zstd_writer:
                with tarfile.open(fileobj=zstd_writer, mode="w|") as tar:
                    files = []
                    for item in current_dir.rglob("*"):
                        if ".git" in item.parts or item.name.endswith(".tar.zst"):
                            continue
                        files.append(item)
                    for file_path in files:
                        tar.add(file_path, arcname=file_path.relative_to(parent_dir))
        if archive_path.exists() and archive_path.stat().st_size > 0:
            shutil.rmtree(current_dir)
        else:
            sys.exit(1)
    except Exception as e:
        sys.exit(1)


if __name__ == "__main__":
    create_archive_streaming_multithreaded()
