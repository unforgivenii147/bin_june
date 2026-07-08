#!/data/data/com.termux/files/usr/bin/env python


import operator
import sys
from pathlib import Path
from dh import fsz, get_files

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
    max_path_len = max(len(str(path)) for path, size in top_files)
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
