#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import sys
from pathlib import Path
from fastwalk import walk_files

RM = "-r" in sys.argv


def get_files(directory: Path):
    for path in walk_files(directory):
        if ".git" in path.parts:
            continue
        if path.is_symlink():
            yield path


if __name__ == "__main__":
    cwd = Path.cwd()
    broken_links = []

    for path in get_files(cwd):
        if not path.exists():
            rel_path = path.relative_to(cwd)
            broken_links.append(str(rel_path))
            print(rel_path)
            if RM:
                try:
                    path.unlink()
                    print(f"Removed: {rel_path}")
                except Exception as e:
                    print(f"Error deleting {path}: {e}")

    bcount = len(broken_links)
    if not bcount:
        print("No broken links found.")
        sys.exit(0)
    if RM:
        print(f"\n{bcount} broken link{'s' if bcount > 1 else ''} removed.")
    else:
        print(f"\n{bcount} broken link{'s' if bcount > 1 else ''} found. Use -r to remove them.")
