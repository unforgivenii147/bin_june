#!/data/data/com.termux/files/usr/bin/env python

"""Module for rmbash.py."""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

from loguru import logger


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


def strip_bash_comments(line):
    if line.startswith("#!"):
        return line, 0
    in_single_quote = False
    in_double_quote = False
    for i, char in enumerate(line):
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif char == "#" and not in_single_quote and not in_double_quote:
            return line[:i].rstrip() + "\n", 1
    return line, 0


def process_file(args):
    path, root = args
    path = Path(path)
    try:
        rel_path = path.relative_to(root)
        lines = path.read_text().splitlines(keepends=True)

        cleaned_lines = []
        total_removed = 0

        for line in lines:
            cleaned, count = strip_bash_comments(line)
            cleaned_lines.append(cleaned)
            total_removed += count

        if total_removed > 0:
            path.write_text("".join(cleaned_lines))
            logger.info(f"{rel_path}: removed {total_removed} comments")
            return total_removed

        return 0
    except Exception as e:
        logger.error(f"Failed {path}: {e}")
        return 0


def main():
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []

    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_files(p))
    else:
        files = get_files(cwd)
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)

    results = mpf3(process_file, files)
    total = 0
    for res in results:
        total += res
    print(f"{total} comments removed")


if __name__ == "__main__":
    sys.exit(main())
