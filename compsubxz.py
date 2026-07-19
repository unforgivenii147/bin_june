#!/data/data/com.termux/files/usr/bin/env python

"""
Compress/decompress subdirectories using tar + lzma with parallel processing.
Usage: script.py -c [paths...]
       script.py -d [paths...]
"""

from __future__ import annotations

import argparse
import lzma
import os
import shutil
import tarfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def iter_target_dirs(paths, recursive=True):
    out = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        if p.is_dir():
            out.append(p)
            if recursive:
                for root, dirs, _ in os.walk(p):
                    root_p = Path(root)
                    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                    for d in dirs:
                        rp = root_p / d
                        if rp.is_dir():
                            out.append(rp)
        elif p.is_file() and p.name.endswith(".tar.lzma"):
            continue
    seen = set()
    uniq = []
    for d in out:
        k = str(d.resolve())
        if k not in seen:
            seen.add(k)
            uniq.append(d)
    return uniq


def iter_target_archives(paths):
    out = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        if p.is_file() and p.name.endswith(".tar.lzma"):
            out.append(p)
        elif p.is_dir():
            for f in p.rglob("*.tar.lzma"):
                if f.is_file():
                    out.append(f)
    seen = set()
    uniq = []
    for a in out:
        k = str(a.resolve())
        if k not in seen:
            seen.add(k)
            uniq.append(a)
    return uniq


def dir_size_bytes(path):
    total = 0
    path = Path(path)
    for root, dirs, files in os.walk(path):
        root_p = Path(root)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            fp = root_p / name
            try:
                st = fp.stat()
                total += st.st_size
            except OSError:
                continue
    return total


def compress_directory(subdir, preset):
    subdir = Path(subdir)
    tar_lzma_path = subdir.parent / f"{subdir.name}.tar.xz"
    try:
        original_size = dir_size_bytes(subdir)
        with lzma.open(tar_lzma_path, "wb", preset=preset) as lzma_out:
            with tarfile.open(fileobj=lzma_out, mode="w|") as tar:
                tar.add(str(subdir), arcname=subdir.name, recursive=True)

        if not tar_lzma_path.exists() or tar_lzma_path.stat().st_size == 0:
            raise RuntimeError("Archive creation failed or empty")

        shutil.rmtree(subdir)
        compressed_size = tar_lzma_path.stat().st_size
        return {
            "success": True,
            "name": subdir.name,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "space_freed": original_size - compressed_size,
        }
    except Exception as e:
        try:
            if tar_lzma_path.exists():
                tar_lzma_path.unlink()
        except OSError:
            pass
        return {"success": False, "name": subdir.name, "error": str(e)}


def is_within_directory(directory, target):
    directory = Path(directory).resolve()
    target = Path(target).resolve()
    return directory == target or directory in target.parents


def safe_extract_stream(tar, dest_dir):
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for member in tar:
        if member is None:
            continue
        name = member.name
        target_path = dest_dir / name
        if not is_within_directory(dest_dir, target_path):
            continue
        tar.extract(member, path=str(dest_dir))


def decompress_archive(archive_path):
    archive_path = Path(archive_path)
    try:
        archive_size = archive_path.stat().st_size

        with lzma.open(archive_path, "rb") as lzma_in, tarfile.open(fileobj=lzma_in, mode="r|") as tar:
            extracted_size = 0
            for member in tar:
                if member is None:
                    continue
                extracted_size += int(getattr(member, "size", 0) or 0)
                break

        extracted_root_name = archive_path.stem
        target_dir = archive_path.parent / extracted_root_name

        with lzma.open(archive_path, "rb") as lzma_in, tarfile.open(fileobj=lzma_in, mode="r|") as tar:
            safe_extract_stream(tar, target_dir)

        archive_path.unlink()
        extracted_size = 0
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            root_p = Path(root)
            for name in files:
                fp = root_p / name
                try:
                    extracted_size += fp.stat().st_size
                except OSError:
                    continue

        space_used = extracted_size - archive_size
        return {
            "success": True,
            "name": archive_path.name,
            "archive_size": archive_size,
            "extracted_size": extracted_size,
            "space_used": space_used,
        }
    except Exception as e:
        return {"success": False, "name": archive_path.name, "error": str(e)}


def format_size(size_bytes):
    size_bytes = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def main():
    parser = argparse.ArgumentParser(description="Compress/decompress subdirectories with tar+lzma")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--compress", action="store_true", help="Compress directories to .tar.lzma")
    group.add_argument("-d", "--decompress", action="store_true", help="Decompress .tar.lzma back to directories")

    parser.add_argument("paths", nargs="*", default=None, help="Files/dirs to process (default: .)")
    parser.add_argument("--preset", type=int, default=9, help="lzma preset (default: 9)")
    parser.add_argument("--no-recursive", action="store_true", help="Disable recursive scan for inputs")
    parser.add_argument("--workers", type=int, default=0, help="Max parallel workers (0=auto)")

    args = parser.parse_args()
    paths = args.paths if args.paths else ["."]

    preset = int(args.preset)
    if preset < 0:
        preset = 0
    if preset > 9:
        preset = 9

    if args.compress:
        worker_count = args.workers if args.workers and args.workers > 0 else (os.cpu_count() or 1)
        recursive = not args.no_recursive
        subdirs = iter_target_dirs(paths, recursive=recursive)
        subdirs = [d for d in subdirs if d.is_dir()]

        if not subdirs:
            print("No subdirectories found to compress.")
            return

        print(f"Found {len(subdirs)} directories to compress.")
        print(f"Starting compression with lzma preset {preset}...")

        total_original = 0
        total_compressed = 0
        successful = 0
        failed = 0

        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(compress_directory, d, preset): d for d in subdirs}
            for fut in as_completed(futures):
                d = futures[fut]
                try:
                    result = fut.result()
                except Exception as e:
                    failed += 1
                    print(f"✗ {Path(d).name}: Failed - {e}")
                    continue

                if result.get("success"):
                    successful += 1
                    total_original += int(result["original_size"])
                    total_compressed += int(result["compressed_size"])
                    print(
                        f"✓ {result['name']}: {format_size(result['original_size'])} -> {format_size(result['compressed_size'])} "
                        f"(freed {format_size(result['space_freed'])})"
                    )
                else:
                    failed += 1
                    print(f"✗ {result.get('name', Path(d).name)}: Failed - {result.get('error')}")

        print(f"\n{'=' * 60}")
        print(f"Compression complete: {successful} successful, {failed} failed")
        if successful > 0:
            total_freed = total_original - total_compressed
            compression_ratio = (1 - total_compressed / total_original) * 100 if total_original else 0.0
            print(f"Total original size:   {format_size(total_original)}")
            print(f"Total compressed size: {format_size(total_compressed)}")
            print(f"Total space freed:     {format_size(total_freed)}")
            print(f"Compression ratio:     {compression_ratio:.1f}%")

    elif args.decompress:
        worker_count = args.workers if args.workers and args.workers > 0 else (os.cpu_count() or 1)
        archives = iter_target_archives(paths)
        archives = [a for a in archives if a.is_file()]

        if not archives:
            print("No .tar.lzma files found to decompress.")
            return

        print(f"Found {len(archives)} archives to decompress.")
        print("Starting decompression...")

        total_archive = 0
        total_extracted = 0
        successful = 0
        failed = 0

        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(decompress_archive, a): a for a in archives}
            for fut in as_completed(futures):
                a = futures[fut]
                try:
                    result = fut.result()
                except Exception as e:
                    failed += 1
                    print(f"✗ {Path(a).name}: Failed - {e}")
                    continue

                if result.get("success"):
                    successful += 1
                    total_archive += int(result["archive_size"])
                    total_extracted += int(result["extracted_size"])
                    space_change = int(result["space_used"])
                    if space_change >= 0:
                        change_str = f"(space used: +{format_size(space_change)})"
                    else:
                        change_str = f"(space freed: {format_size(-space_change)})"
                    print(
                        f"✓ {result['name']}: {format_size(result['archive_size'])} -> {format_size(result['extracted_size'])} {change_str}"
                    )
                else:
                    failed += 1
                    print(f"✗ {result.get('name', Path(a).name)}: Failed - {result.get('error')}")

        print(f"\n{'=' * 60}")
        print(f"Decompression complete: {successful} successful, {failed} failed")
        if successful > 0:
            total_change = total_extracted - total_archive
            print(f"Total archive size:     {format_size(total_archive)}")
            print(f"Total extracted size:   {format_size(total_extracted)}")
            print(f"Net space change:       {format_size(total_change)}")


if __name__ == "__main__":
    main()
