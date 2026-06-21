#!/data/data/com.termux/files/usr/bin/python

import compileall
import sys
from collections import deque
from multiprocessing import get_context
from pathlib import Path

from dh import get_files, gsz

MAX_QUEUE = 4
REMOVE_ORIG = False


def process_file(path) -> bool | None:
    path = Path(path)
    if not path.exists():
        return False
    if ".git" in path.parts:
        return None
    if path.is_dir():
        for f in path.rglob("*.py"):
            process_file(f)
    if path.is_file() and (not path.is_symlink()):
        pyc_file = path.with_suffix(".pyc")
        if pyc_file.exists():
            pyc_file.unlink()
        compileall.compile_file(path, optimize=0)
        if REMOVE_ORIG:
            path.unlink()
        return True
    return False


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(f) for f in args] if args else get_files(cwd, ext=[".py"])
    with get_context("spawn").Pool(4) as pool:
        pending = deque()
        for f in files:
            pending.append(pool.apply_async(process_file, (f,)))
            if len(pending) > MAX_QUEUE:
                pending.popleft().get()
        while pending:
            pending.popleft().get()


if __name__ == "__main__":
    main()
