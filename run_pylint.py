#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from os import scandir as os_scandir
from pathlib import Path
from dh.fileutils import runcmd
from dh.fileutils import is_python_file
from dh.fileutils import is_binary
from dh.fileutils import get_pyfiles

CHUNK_SIZE = 1024 * 1024

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def process_file(path) -> None:
    path = Path(path)
    cmd = [
        "pylint",
        f"{path!s}",
        "--persistent=n",
        "--reports=n",
        "--output-format=parseable",
        "--msg-template='{C}:{line}:{column}:{obj}:{msg}:{msg_id}'",
        str(path),
    ]
    return runcmd(cmd, show_output=True)


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            if p.is_dir():
                files.extend(get_pyfiles(p))
    else:
        files = get_pyfiles(cwd)
    for f in files:
        process_file(f)


if __name__ == "__main__":
    sys.exit(main())
