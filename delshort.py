#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path
from dh import get_files, is_binary

SIZE_THRESHOLD = 100
LINE_THRESHOLD = 3


def process_file(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    if path.stat().st_size < SIZE_THRESHOLD and len(path.read_text().splitlines()) < LINE_THRESHOLD:
        path.unlink()
        print(f"{path.name} removed")


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
