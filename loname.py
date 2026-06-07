#!/data/data/com.termux/files/usr/bin/python

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


def process_file(path):
    if not path.exists():
        path = Path(str(path).lower())
        if not path.exists():
            return
    new_name = path.name.lower()
    if new_name == path.name:
        return
    new_path = path.with_name(new_name)
    if new_path.exists():
        new_path = unique_path(new_path)
    path.rename(new_path)
    print(f"{path.name} -> {new_path.name}")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = list(cwd.glob("*")) if args else list(cwd.rglob("*"))
    for f in files:
        process_file(f)
