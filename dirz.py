#!/data/data/com.termux/files/usr/bin/python

from pathlib import Path


def gsz(fp):
    if fp.is_dir():
        return sum((p.stat().st_size for p in fp.rglob("*") if p.is_file() and (not p.is_symlink())))
    if fp.is_file():
        return fp.stat().st_size
    return None


def fsz(k):
    if k > 1024 * 1024:
        return f"{k / (1024 * 1024):.1f} MB"
    return f"{k / 1024:.1f} KB"


if __name__ == "__main__":
    cwd = Path.cwd()
    for path in cwd.glob("*"):
        if path.is_dir():
            print(f"  -  {path.name}      {fsz(gsz(path))}")
