#!/data/data/com.termux/files/usr/bin/env python


import operator
import sys
from os import scandir as os_scandir
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = "B", "KB", "MB", "GB", "TB"
    if sz == 0:
        return "0 B"
    i = min((int(sz).bit_length() - 1) // 10, len(units) - 1)
    value = sz / 1024**i
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


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
