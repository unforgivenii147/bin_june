#!/data/data/com.termux/files/home/.local/bin/python

"""
Folder compressor/decompressor using LZ4 with multiprocessing
Usage:
    python script.py            # Compress all subfolders (default)
    python script.py -c         # Compress all subfolders
    python script.py -d         # Decompress all .tar.lz4 files
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import tarfile
from multiprocessing import Pool, cpu_count
from pathlib import Path

import lz4.frame

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_folder_size(folder_path):
    total = 0
    for dirpath, _dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total += os.path.getsize(fp)
    return total


def format_size(bytes_size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def compress_folder(folder_path):
    folder = Path(folder_path)
    if not folder.is_dir():
        return f"Skipped {folder}: Not a directory"
    tar_lz4_path = folder.with_suffix(".tar.lz4")
    if tar_lz4_path.exists():
        return f"Skipped {folder}: Already compressed"
    try:
        original_size = get_folder_size(folder)
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            tar.add(folder, arcname=folder.name)
        tar_data = tar_buffer.getvalue()
        compressed = lz4.frame.compress(tar_data, compression_level=3)
        with open(tar_lz4_path, "wb") as f:
            f.write(compressed)
        compressed_size = tar_lz4_path.stat().st_size
        shutil.rmtree(folder)
        ratio = original_size / compressed_size if compressed_size > 0 else 0
        space_freed = original_size - compressed_size
        compression_percent = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        return {
            "folder": folder.name,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "space_freed": space_freed,
            "ratio": ratio,
            "compression_percent": compression_percent,
            "status": "success",
        }
    except Exception as e:
        return {"folder": folder.name, "error": str(e), "status": "error"}


def decompress_file(file_path):
    file = Path(file_path)
    if not file.suffix == ".lz4" or not file.stem.endswith(".tar"):
        return f"Skipped {file}: Not a tar.lz4 file"
    folder_name = file.stem[:-4]
    folder_path = file.parent / folder_name
    if folder_path.exists():
        return f"Skipped {file}: Already decompressed"
    try:
        with open(file, "rb") as f:
            compressed_data = f.read()
        decompressed = lz4.frame.decompress(compressed_data)
        tar_buffer = io.BytesIO(decompressed)
        with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
            tar.extractall(path=file.parent, filter="data")
        file.unlink()
        return f"Decompressed: {file} -> {folder_path}"
    except Exception as e:
        return f"Error decompressing {file}: {e}"


def print_compression_report(results):
    successful = [r for r in results if r.get("status") == "success"]
    errors = [r for r in results if r.get("status") == "error"]
    if not successful:
        print("No folders were compressed successfully")
        return
    print("\n" + "=" * 80)
    print("COMPRESSION REPORT")
    print("=" * 80)
    print(f"{'Folder':<20} {'Original':<12} {'Compressed':<12} {'Freed':<12} {'Ratio':<10} {'Saved %':<10}")
    print("-" * 80)
    total_original = 0
    total_compressed = 0
    total_freed = 0
    for r in successful:
        total_original += r["original_size"]
        total_compressed += r["compressed_size"]
        total_freed += r["space_freed"]
        print(
            f"{r['folder']:<20} {format_size(r['original_size']):<12} {format_size(r['compressed_size']):<12} {format_size(r['space_freed']):<12} {r['ratio']:>6.2f}x   {r['compression_percent']:>6.1f}%"
        )
    print("-" * 80)
    print(
        f"{'TOTAL':<20} {format_size(total_original):<12} {format_size(total_compressed):<12} {format_size(total_freed):<12} {(total_original / total_compressed if total_compressed > 0 else 0):>6.2f}x   {((1 - total_compressed / total_original) * 100 if total_original > 0 else 0):>6.1f}%"
    )
    print("=" * 80)
    if errors:
        print("\nERRORS:")
        for r in errors:
            print(f"  {r['folder']}: {r['error']}")
        print("=" * 80)
    print(f"\nTotal space freed: {format_size(total_freed)}")
    print(f"Average compression ratio: {(total_original / total_compressed if total_compressed > 0 else 0):.2f}x")


def main():
    parser = argparse.ArgumentParser(
        description="Compress/decompress folders with LZ4",
        epilog="Default action: compress subfolders in current directory",
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-c", "--compress", action="store_true", help="Compress subfolders")
    group.add_argument("-d", "--decompress", action="store_true", help="Decompress .tar.lz4 files")
    args = parser.parse_args()
    current_dir = Path.cwd()
    if not args.compress and (not args.decompress):
        args.compress = True
    if args.compress:
        items = [d for d in current_dir.iterdir() if d.is_dir()]
        process_func = compress_folder
        action = "Compressing"
    else:
        items = [f for f in current_dir.iterdir() if f.is_file() and f.suffix == ".lz4" and f.stem.endswith(".tar")]
        process_func = decompress_file
        action = "Decompressing"
    if not items:
        print(f"No {('folders' if args.compress else '.tar.lz4 files')} found")
        return
    print(f"{action} {len(items)} items using {cpu_count()} processes...")
    with Pool(processes=cpu_count()) as pool:
        results = pool.map(process_func, items)
    if args.compress:
        print_compression_report(results)
    else:
        for result in results:
            print(result)
        print(f"\n{action} complete!")


if __name__ == "__main__":
    main()
