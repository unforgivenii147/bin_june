#!/data/data/com.termux/files/usr/bin/env python
from __future__ import annotations

import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


CHUNKSIZE = 15850


def process_file(path):
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as infile:
            part_num = 0
            while True:
                chunk = infile.read(CHUNKSIZE)
                if not chunk:
                    break
                outpath = path.with_stem(path.stem + "_" + str(part_num))
                outpath.write_text(chunk, encoding="utf-8")
                part_num += 1
    except Exception as e:
        print(f"An error occurred during file splitting: {e}")


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
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


CHUNKSIZE = 15850


def process_file(path):
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as infile:
            part_num = 0
            while True:
                chunk = infile.read(CHUNKSIZE)
                if not chunk:
                    break
                outpath = path.with_stem(path.stem + "_" + str(part_num))
                outpath.write_text(chunk, encoding="utf-8")
                part_num += 1
    except Exception as e:
        print(f"An error occurred during file splitting: {e}")


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
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
