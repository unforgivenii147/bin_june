#!/data/data/com.termux/files/usr/bin/python

import compileall
import sys
from collections import deque
from multiprocessing import get_context
from pathlib import Path

from dh import fsz, get_files, gsz

MAX_QUEUE = 16


def process_file(fp):
    path = Path(path)
    if not fp.exists():
        return False
    if ".git" in fp.parts:
        return None
    compileall.compile_file(fp, legacy=True, optimize=2)
    return True


def main():
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(f) for f in args] if args else get_files(cwd, ext=[".py"])
    with get_context("spawn").Pool(8) as pool:
        pending = deque()
        for f in files:
            pending.append(pool.apply_async(process_file, (f,)))
            if len(pending) > MAX_QUEUE:
                pending.popleft().get()
        while pending:
            pending.popleft().get()
    diff_size = before - gsz(cwd)
    print(f"space changed : {fsz(diff_size)}")


if __name__ == "__main__":
    main()
