#!/data/data/com.termux/files/usr/bin/python

import os
import shutil
import sys
from pathlib import Path


def replace_in_file(path: str, old: str, new: str) -> None:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except (UnicodeDecodeError, PermissionError):
        return
    if old not in text:
        return
    new_text = text.replace(old, new)
    Path(path).write_text(new_text, encoding="utf-8")


def rename_path(path: str, old: str, new: str) -> str:
    dirname = Path(path).parent
    basename = Path(path).name
    if old not in basename:
        return path
    new_basename = basename.replace(old, new)
    new_path = os.path.join(dirname, new_basename)
    if Path(new_path).exists():
        print(f"path by name {new_path} already exists\n rename it manually")
        return path
    try:
        shutil.move(path, new_path)
        return new_path
    except Exception:
        return path


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <text_to_change> <replacement_text>")
        sys.exit(1)
    old = sys.argv[1]
    new = sys.argv[2]
    for root, _, files in os.walk(".", topdown=True):
        for fn in files:
            replace_in_file(os.path.join(root, fn), old, new)
    for root, dirs, files in os.walk(".", topdown=False):
        for fn in files:
            rename_path(os.path.join(root, fn), old, new)
        for dn in dirs:
            rename_path(os.path.join(root, dn), old, new)


if __name__ == "__main__":
    main()
