#!/data/data/com.termux/files/usr/bin/python

import shutil
from pathlib import Path


def fsz(sz) -> str:
    sz = abs(int(sz))
    units = ("", "K", "M", "G", "T")
    if sz == 0:
        return "0 B"
    i = min(int(int(sz).bit_length() - 1) // 10, len(units) - 1)
    sz /= 1024**i
    return f"{sz:.2f} {units[i]}B"


def gsz(path: Path) -> int:
    return sum((p.stat().st_size for p in path.rglob("*") if p.is_file()))


def clean_pycache(start_dir: Path = Path.cwd()):
    removed = 0
    sz = 0
    for path in start_dir.rglob("__pycache__"):
        if path.exists():
            sz += gsz(path)
            removed += 1
            shutil.rmtree(str(path))
    if removed:
        print(f"   • Total size freed: {fsz(sz)}")
        print(f"   • dirs removed: {removed}")
    else:
        print("nothing found.")


if __name__ == "__main__":
    cwd = Path.cwd()
    clean_pycache(cwd)
