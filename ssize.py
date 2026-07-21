#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import operator
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

total = 0


def gsz(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink())


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = "", "K", "M", "G", "T"
    if sz == 0:
        return "0 B"
    i = min(int(int(sz).bit_length() - 1) // 10, len(units) - 1)
    sz /= 1024**i
    return f"{sz:.2f} {units[i]}B"


def list_and_sort_by_size(path: Path = Path()):
    items = []
    global total
    for p in path.glob("*"):
        if p.is_symlink():
            continue
        size = gsz(p)
        total += size
        items.append({"name": p.name, "size": size})
    items.sort(key=operator.itemgetter("size"), reverse=False)
    return items


if __name__ == "__main__":
    data = list_and_sort_by_size()
    for k in data:
        print(f"{k['name']} : \x1b[5;96m {fsz(k['size'])}\x1b[0m")
    print(f"\ntotal:\x1b[5;94m {fsz(total)}\x1b[0m")
