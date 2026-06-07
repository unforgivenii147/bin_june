#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import get_files, is_binary

cwd = Path.cwd()
bin_dir = Path(f"{cwd}/binary")
bin_dir.mkdir(exist_ok=True)


def process_file(fp) -> None:
    if is_binary(fp):
        newpath = bin_dir / fp.name
        fp.rename(newpath)


def main():
    files = get_files(cwd)
    for f in files:
        process_file(f)


if __name__ == "__main__":
    sys.exit(main())
