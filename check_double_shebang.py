#!/data/data/com.termux/files/usr/bin/env python

"""Module for check_double_shebang.py."""

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


def process_file(path: Path) -> None:
    path = Path(path)
    if path.is_symlink():
        return
    content = path.read_text()
    lines = content.splitlines()
    c = 0
    for line in lines:
        if line.startswith("#!"):
            c += 1
    if c > 1:
        print(path.name)


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            if p.is_dir():
                files.extend(get_files(p))
    else:
        files = get_files(cwd, ext=[".py"])
    for f in files:
        process_file(f)


if __name__ == "__main__":
    sys.exit(main())
