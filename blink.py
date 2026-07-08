#!/data/data/com.termux/files/usr/bin/env python
import sys
from pathlib import Path


def get_files(directory: Path):
    for fullpath in directory.rglob("*"):
        if ".git" in fullpath.parts:
            continue
        if fullpath.is_symlink():
            yield fullpath


if __name__ == "__main__":
    cwd = Path.cwd()
    bcount = 0
    for path in get_files(cwd):
        if not path.exists():
            try:
                path.unlink()
                bcount += 1
                print(f"{path.relative_to(cwd)}")
            except Exception as e:
                print(f"Error deleting {path}: {e}")
    if not bcount:
        print("no broken link found.")
        sys.exit(0)
    print(f"{bcount} broken link removed.")
