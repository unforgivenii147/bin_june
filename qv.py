#!/data/data/com.termux/files/usr/bin/env python


import pathlib
import pydoc
import sys


def view_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        pydoc.pager(content)


def main():
    recursive = "-r" in sys.argv
    current_dir = pathlib.Path(".")
    if recursive:
        files = current_dir.rglob("*")
    else:
        files = current_dir.glob("*")
    files = [f for f in files if f.is_file()]
    for file_path in files:
        print(f"Viewing: {file_path}")
        view_file(file_path)


if __name__ == "__main__":
    main()
