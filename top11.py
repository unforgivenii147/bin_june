#!/data/data/com.termux/files/usr/bin/env python

"""Module for top11.py."""
from __future__ import annotations

import operator
import sys
from collections import deque
from pathlib import Path


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = ("B", "KB", "MB", "GB", "TB")
    if sz == 0:
        return "0 B"
    i = min((int(sz).bit_length() - 1) // 10, len(units) - 1)
    value = sz / 1024**i
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


cwd = Path.cwd()
N = int(sys.argv[1])


def get_sizes() -> list[tuple[Path, int]]:
    return [(file_path.relative_to(cwd), file_path.stat().st_size) for file_path in get_files(cwd)]


def main() -> None:
    sizez = get_sizes()
    if not sizez:
        print("No files found or unable to access directory.")
        return
    sizez.sort(key=operator.itemgetter(1), reverse=True)
    num_files = N or 10
    top_files = sizez[:num_files]
    print("\n" + "=" * 35)
    print(f"TOP 10 LARGEST FILES (in {Path.cwd()})")
    print("=" * 35)
    if not top_files:
        print("No files found.")
        return
    max_path_len = max((len(str(path)) for path, size in top_files))
    max_path_len = min(max_path_len, 80)
    print(f"{'No.':<4} {'File Path':<{max_path_len}} {'Size':>12}")
    print("-" * (max_path_len + 20))
    for i, (file_path, size) in enumerate(top_files, 1):
        path_str = str(file_path)
        if len(path_str) > max_path_len:
            path_str = "..." + path_str[-(max_path_len - 3) :]
        size_str = fsz(size)
        print(f"{i:<4} {path_str:<{max_path_len}} {size_str:>12}")
    total_files = len(sizez)
    print("-" * (max_path_len + 20))
    print(f"Total files scanned: {total_files}")
    if total_files > 10:
        print(f"Showing top 10 out of {total_files} files")


def m2() -> None:
    sizez = get_sizes()
    if not sizez:
        print("No files found.")
        return
    sizez.sort(key=operator.itemgetter(1), reverse=True)
    num_files = N or 10
    top_files = sizez[:num_files]
    print("\nTOP 10 LARGEST FILES (Detailed View)")
    print("=" * 35)
    for i, (file_path, size) in enumerate(top_files, 1):
        size_str = fsz(size)
        print(f"{i:2d}. {size_str:>10} - {file_path.relative_to(cwd)}")


if __name__ == "__main__":
    main()
