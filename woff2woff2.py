#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

from dh import cprint
from fontTools.ttLib import TTFont
from dh.fileutils import unique_path
from dh.fileutils import _clean_fname
from dh.jobutils import mpf3


cwd = Path.cwd()


def process_file(path: Path) -> None:
    path = Path(path)
    woff2_path = path.with_suffix(".woff2")
    if woff2_path.exists() and woff2_path.stat().st_size:
        woff2_path = unique_path(woff2_path)
    try:
        font = TTFont(path)
        font.flavor = "woff2"
        font.save(woff2_path)
        print(f"{path.name} converted.")
        path.unlink()
    except:
        cprint(f"error convering {path.name}")


def main() -> None:
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".woff"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
