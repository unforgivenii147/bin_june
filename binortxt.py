#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path
from dh import get_files, is_binary, mpf3

cwd = Path.cwd()
bin_dir = Path(f"{cwd}/binary")
bin_dir.mkdir(exist_ok=True)


def process_file(fp) -> None:
    path = Path(path)
    if is_binary(fp):
        newpath = bin_dir / fp.name
        fp.rename(newpath)


def main() -> None:
    files = get_files(cwd)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
