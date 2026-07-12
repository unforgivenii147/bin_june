#!/data/data/com.termux/files/usr/bin/env python
import operator
import os
import stat
import sys
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


CYAN = "\x1b[36m"
BLUE = "\x1b[34m"
GREEN = "\x1b[32m"
RED = "\x1b[31m"
RESET = "\x1b[0m"
COMPRESSED_EXTS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z"}


def human_readable_size(size_bytes) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    return f"{size_bytes / 1024**3:.1f} GB"


def get_dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                path = os.path.join(root, f)
                if Path(path).is_file():
                    total += Path(path).stat().st_size
            except Exception:
                pass
    return total


def list_dir(path: str = ".") -> None:
    entries = os.listdir(path)
    items = []
    for entry in entries:
        full_path = os.path.join(path, entry)
        try:
            if Path(full_path).is_dir():
                size = get_dir_size(full_path)
                color = BLUE
            else:
                size = Path(full_path).stat().st_size
                mode = os.stat(full_path).st_mode
                ext = os.path.splitext(entry)[1].lower()
                if ext in COMPRESSED_EXTS:
                    color = RED
                elif mode & stat.S_IXUSR:
                    color = GREEN
                else:
                    color = CYAN
        except Exception:
            size = 0
            color = CYAN
        items.append((size, entry, color))
    size_col_width = max(len(human_readable_size(s)) for s, _, _ in items)
    name_col_width = max(len(n) for _, n, _ in items)
    print(f"{'size'.ljust(size_col_width)}  {'name'}")
    print("-" * (size_col_width + name_col_width + 2))
    for size, name, color in sorted(items, key=operator.itemgetter(0)):
        size_str = human_readable_size(size).ljust(size_col_width)
        print(f"{size_str}  {color}{name}{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        list_dir(sys.argv[1])
    else:
        list_dir(".")
