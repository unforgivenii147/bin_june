#!/data/data/com.termux/files/usr/bin/env python

"""Module for h2md.py."""
from __future__ import annotations

import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

from markdownify import markdownify


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


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


def process_file(path) -> None:
    path = Path(path)
    md_path = path.with_suffix(".md")
    content = path.read_text(encoding="utf8")
    markdownify(content)
    md_path.write_text(md_content, encoding="utf-8")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_files(p, ext=[".html"]))
    else:
        files.extend(get_files(p, ext=[".html"]))
    mpf3(process_file, files)
