#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import sys
from pathlib import Path

RM = "-r" in sys.argv


def get_files(directory: Path):
    for root, _, files in directory.walk():
        for f in files:
            fullpath = Path(root) / f

            if ".git" in fullpath.parts:
                continue
            if fullpath.is_symlink():
                yield fullpath


if __name__ == "__main__":
    cwd = Path.cwd()
    broken_links = []

    for path in get_files(cwd):
        if not path.exists():
            rel_path = path.relative_to(cwd)
            broken_links.append(str(rel_path))
            if RM:
                try:
                    path.unlink()
                    print(f"Removed: {rel_path}")
                except Exception as e:
                    print(f"Error deleting {path}: {e}")

    bcount = len(broken_links)
    if not bcount:
        print("No broken symlink")
        sys.exit(0)
    if RM:
        print(f"\n{bcount} broken link{'s' if bcount > 1 else ''} removed.")
    else:
        print(f"\n{bcount} broken link{'s' if bcount > 1 else ''} found. Use -r to remove them.")
