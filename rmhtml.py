#!/data/data/com.termux/files/usr/bin/python

import re
import sys
from pathlib import Path

from dh import cprint, fsz, get_files, gsz, mpf3

MAX_QUEUE = 16


def process_file(fp) -> None:
    before = gsz(fp)
    src = fp.read_text(encoding="utf-8")
    pattern = re.compile("<!--[\\s\\S]*?-->", re.MULTILINE)
    out = pattern.sub("", src)
    if out != src:
        code = out.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        fp.write_text(code, encoding="utf-8")
    after = gsz(fp)
    print(f"[OK] {fp.name} ", end="")
    diffsize = before - after
    cprint(f"{fsz(diffsize)}", "cyan")


def main():
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(f) for f in args] if args else get_files(cwd, ext=[".html", ".htm", ".xml"])
    mpf3(process_file, files)
    diff_size = before - gsz(cwd)
    print(f"space saved : {fsz(diff_size)}")


if __name__ == "__main__":
    main()
