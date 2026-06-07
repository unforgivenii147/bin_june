#!/data/data/com.termux/files/usr/bin/python

import shutil
import sys
from pathlib import Path

dest = Path.home() / "isaac" / "may" / "scripts"


def unique_path(path: Path | str) -> Path:
    path = Path(path)
    if not path.exists():
        return path
    parent = path.parent
    suffixes = path.suffixes
    if suffixes:
        first_suffix_index = path.name.find(suffixes[0])
        stem = path.name[:first_suffix_index]
        full_suffix = "".join(suffixes)
    else:
        stem = path.name
        full_suffix = ""
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{full_suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def main():
    fn = Path(sys.argv[1])
    dest_path = dest / fn.name
    if dest_path.exists():
        dest_path = unique_path(dest_path)
    shutil.move(str(fn), str(dest_path))
    print(f"{fn.name} --> {dest_path.name}")


if __name__ == "__main__":
    sys.exit(main())
