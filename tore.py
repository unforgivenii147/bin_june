#!/data/data/com.termux/files/usr/bin/python

import shutil
import sys
from pathlib import Path


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


if __name__ == "__main__":
    src = Path(sys.argv[1]).resolve()
    cwd = Path.home() / "repos"
    dst = cwd / src.name
    if dst.exists():
        dst = unique_path(dst)
    shutil.move(str(src), str(dst))
    print(f"{src.name} --> {dst.name}")
