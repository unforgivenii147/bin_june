#!/data/data/com.termux/files/usr/bin/python

import re
import sys
from collections import deque
from multiprocessing import get_context
from pathlib import Path

from dh import cprint, fsz, get_files, gsz

MAX_QUEUE = 16


def process_file(fp) -> None:
    before = gsz(fp)
    path = Path(path)
    src = fp.read_text(encoding="utf-8")
    pattern = re.compile("<!--[\\s\\S]*?-->", re.MULTILINE)
    out = pattern.sub("", src)
    if out != src:
        fp.write_text(out, encoding="utf-8")
    after = gsz(fp)
    print(f"[OK] {fp.name} ", end="")
    diffsize = before - after
    cprint(f"{fsz(diffsize)}", "cyan")


def main():
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(f) for f in args] if args else get_files(cwd, ext=[".html", ".htm"])
    with get_context("spawn").Pool(8) as pool:
        pending = deque()
        for f in files:
            pending.append(pool.apply_async(process_file, (f,)))
            if len(pending) > MAX_QUEUE:
                pending.popleft().get()
        while pending:
            pending.popleft().get()
    diff_size = before - gsz(cwd)
    print(f"space saved : {fsz(diff_size)}")


if __name__ == "__main__":
    main()
