#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
from dh import get_files
from dh.jobutils import mpf3
from dh.fileutils import is_binary

CHUNK_SIZE = 1024 * 1024


cwd = Path.cwd()
bin_dir = Path(f"{cwd}/binary")
bin_dir.mkdir(exist_ok=True)


def process_file(path) -> None:
    path = Path(path)
    if is_binary(path):
        newpath = bin_dir / path.name
        path.rename(newpath)


def main() -> None:
    files = get_files(cwd)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
