#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import sys
from collections import deque
from pathlib import Path


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


RM = "-r" in sys.argv


def get_files(directory: Path):
    for path in directory.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_symlink():
            yield path


if __name__ == "__main__":
    cwd = Path.cwd()
    bcount = 0
    broken_links = []
    for path in get_files(cwd):
        if not path.exists():
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
