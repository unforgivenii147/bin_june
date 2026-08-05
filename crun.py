#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from dh.fileutils import get_filez
from dh.fileutils import should_skip
from dh.fileutils import fsz
from dh.fileutils import gsz
from dh.jobutils import mpf3

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def process_file(path):
    path = Path(path)
    if not path.exists():
        return False
    if path.suffix == ".c":
        cmd = f"clang {path!s} -o {path.with_suffix('')!s}"
    if path.suffix == ".cpp":
        cmd = f"clang++ {path!s} -o {path.with_suffix('')!s}"
    ret, txt, _err = run_command(cmd)
    print(txt)
    return ret


def main() -> None:
    cwd = Path().cwd()
    start_size = gsz(cwd)
    files = []
    for path in get_filez(cwd):
        if path.is_file() and path.suffix in {".c", ".cpp"}:
            files.append(path)
    mpf3(process_file, files)
    print(f"{fsz(start_size - gsz(cwd))}")


if __name__ == "__main__":
    sys.exit(main())
