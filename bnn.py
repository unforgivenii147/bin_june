#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations
import sys

from pathlib import Path


def process_file(path) -> None:
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    content = content.replace("\\n", "\n")
    path.write_text(content, encoding="utf-8")
    print(f"{path.name} updated.")


if __name__ == "__main__":
    from dh import get_pyfiles, mpf3

    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_pyfiles(cwd)
    mpf3(process_file, files)
