#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import get_files, mpf3
from markdownlify import markdownify


def process_file(fp) -> None:
    pass
    path = Path(path)


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
        files = get_files(cwd)
    with Pbar("") as pbar:
        for f in pbar.wrap(files):
            process_file(f)


if __name__ == "__main__":
    sys.exit(main())
