#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path
from dh import cprint

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


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


if __name__ == "__main__":
    cwd = Path.cwd()
    for path in sorted(cwd.glob("*"), key=lambda e: e.stat().st_mtime):
        mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M")
        if path.is_symlink():
            sz = " symlink "
        elif path.is_file() or path.is_dir():
            sz = str(fsz(gsz(path)))
            match len(sz):
                case 3:
                    sz = "      " + sz
                case 4:
                    sz = "     " + sz
                case 5:
                    sz = "    " + sz
                case 6:
                    sz = "   " + sz
                case 7:
                    sz = "  " + sz
                case 8:
                    sz = " " + sz
        cprint(f"{path.name[:24]:25}", "blue", end=" ")
        cprint(f"{sz}", "cyan", end=" ")
        cprint(f"{mtime}", "yellow")
