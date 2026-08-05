#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from pathlib import Path

from dh import get_fast

RM = "-r" in sys.argv


if __name__ == "__main__":
    cwd = Path.cwd()
    bcount = 0
    broken_links = []
    for path in get_fast(cwd):
        print(path.name)
        bcount += 1
        broken_links.append(str(path.relative_to(cwd)))
        if RM:
            try:
                path.unlink()
                print(f"Removed: {path.relative_to(cwd)}")
            except Exception as e:
                print(f"Error deleting {path}: {e}")
    if broken_links:
        for link in broken_links:
            print(f"{link}\n")
    if not bcount:
        print("no broken link found.")
        sys.exit(0)
    if RM:
        print(f"{bcount} broken link removed.")
    else:
        print(f"{bcount} broken link found. Use -r to remove them.")
