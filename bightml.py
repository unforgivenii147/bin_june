#!/data/data/com.termux/files/usr/bin/env python

"""Module for bightml.py."""
from __future__ import annotations

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


def main() -> None:
    cwd = Path.home()
    files = get_files(cwd, ext=[".html", ".htm"])
    for f in files:
        if f.stat().st_size > 1024 * 1024:
            print(f.relative_to(cwd))


if __name__ == "__main__":
    main()
