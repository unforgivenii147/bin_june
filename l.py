#!/data/data/com.termux/files/usr/bin/python

import datetime
from os import scandir as _scandir
from pathlib import Path


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = ("", "K", "M", "G", "T")
    if sz == 0:
        return "0 B"
    i = min(int(int(sz).bit_length() - 1) // 10, len(units) - 1)
    sz /= 1024**i
    return f"{int(sz)} {units[i]}B"


def gsz(path: str | Path) -> int:
    path = Path(path)
    total_size = 0
    if not path.exists():
        return 0
    if path.is_file():
        try:
            total_size = path.stat().st_size
        except OSError:
            return 0
    elif path.is_dir():
        for entry in _scandir(path):
            try:
                if entry.is_file():
                    total_size += entry.stat().st_size
                elif entry.is_dir():
                    total_size += gsz(entry.path)
            except OSError:
                continue
    return total_size


EXCLUDED = {".mypy_cache", ".ruff_cache", ".git", "__pycache__"}
if __name__ == "__main__":
    cwd = Path.cwd()
    for path in sorted(cwd.rglob("*"), key=lambda e: e.stat().st_mtime):
        if any((pat in path.parts for pat in EXCLUDED)):
            continue
        mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M")
        if path.is_dir():
            continue
        elif path.is_symlink():
            sz = " \x1b[05;95msymlink "
        else:
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
        if path.is_symlink():
            print(f"\x1b[05;95m{path.name[:24]:25}\x1b[0m", end=" ")
        else:
            print(f"\x1b[05;94m{path.name[:24]:25}\x1b[0m", end=" ")
        print(f"\x1b[05;96m{sz}\x1b[0m", end=" ")
        print(f"\x1b[05;93m{mtime}\x1b[0m")
