#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path
from dh import get_files, is_binary

SIZE_THRESHOLD = 100
LINE_THRESHOLD = 3


def process_file(fp: Path) -> None:
    path = Path(path)
    if not fp.exists():
        return
    if fp.stat().st_size < SIZE_THRESHOLD and len(fp.read_text().splitlines()) < LINE_THRESHOLD:
        fp.unlink()
        print(f"{fp.name} removed")


def main() -> None:
    cwd = Path.cwd()
    files = get_files(cwd)
    for path in files:
        if not is_binary(path) and path.exists():
            process_file(path)
        else:
            print(f"{path.name} is binary")


if __name__ == "__main__":
    sys.exit(main())
