#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import pathlib
import pydoc
import sys


def view_file(file_path):
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
        pydoc.pager(content)


def main():
    recursive = "-r" in sys.argv
    cwd = pathlib.Path(".")
    if recursive:
        files = cwd.rglob("*")
    else:
        files = cwd.glob("*")
    files = [f for f in files if f.is_file()]
    for file_path in files:
        print(f"Viewing: {file_path}")
        view_file(file_path)


if __name__ == "__main__":
    main()
