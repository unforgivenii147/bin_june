#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

from dh import cprint
from dh.jobutils import mpf3
from dh.fileutils import is_binary
from dh.fileutils import get_nobinary

CHUNK_SIZE = 1024 * 1024


def process_file(path: str | Path) -> None:
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    new_content = content.replace("\t", "    ")
    if new_content == content:
        cprint(f"{path.name} (no change)", "grey")
        return
    path.write_text(new_content, encoding="utf-8")
    cprint(f"{path.name} (updated)", "cyan")


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_nobinary(p))
    else:
        files = get_nobinary(cwd)
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
