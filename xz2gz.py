#!/data/data/com.termux/files/usr/bin/env python


"""
Convert man pages from .gz to .xz format with maximum compression.
Skips symlinks and processes files recursively in the current directory.
"""

import sys
from collections.abc import Callable, Iterable
from gzip import compress as gzip_compress
from os import scandir as os_scandir
from pathlib import Path
from typing import Tuple

from lzma_mt import decompress

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


def process_file(path: Path) -> Tuple[str, bool, str]:
    path = Path(path)
    if path.is_symlink():
        print("symlink")
        return str(path), False, f"Error: symlink"
    gz_path = path.with_suffix(".gz")
    try:
        data = path.read_bytes()
        decompressed = decompress(data, threads=4)
        compressed = gzip_compress(decompressed, compresslevel=9)
        gz_path.write_bytes(compressed)
        if gz_path.exists() and gz_path.stat().st_size > 0:
            path.unlink()
            original_size = path.stat().st_size if path.exists() else 0
            new_size = gz_path.stat().st_size
            ratio = new_size / original_size * 100 if original_size > 0 else 0
            return (str(path), True, f"Converted to {gz_path.name} ({original_size} -> {new_size} bytes, {ratio:.1f}%)")
        return str(path), False, "Output file is empty or missing"
    except Exception as e:
        if gz_path.exists():
            gz_path.unlink()
        return str(path), False, f"Error: {str(e)}"


def main() -> None:
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".xz"])
    if not files:
        print("No .xz files found to convert.")
        return
    results = mpf3(process_file, files)
    success_count = 0
    failure_count = 0
    total_original = 0
    total_new = 0
    print("\n" + "=" * 70)
    print("CONVERSION RESULTS")
    print("=" * 70)
    for file_path, success, message in results:
        if success:
            success_count += 1
            print(f"✓ {message}")
            if "bytes" in message:
                try:
                    parts = message.split("(")[1].split(")")
                    sizes = parts[0].split("->")
                    total_original += int(sizes[0].strip().split()[0])
                    total_new += int(sizes[1].strip().split()[0])
                except:
                    pass
        else:
            failure_count += 1
            print(f"✗ {file_path}: {message}", file=sys.stderr)
    print("-" * 70)
    print(f"Summary: {success_count} successful, {failure_count} failed")
    print(f"Total files processed: {len(results)}")
    if success_count > 0 and total_original > 0:
        savings = (1 - total_new / total_original) * 100
        print(f"Total space saved: {total_original - total_new:,} bytes ({savings:.1f}%)")
        print(f"Original total: {total_original:,} bytes")
        print(f"New total: {total_new:,} bytes")
    if success_count > 0:
        print("\nNote: Original .xz files have been removed.")


if __name__ == "__main__":
    main()
