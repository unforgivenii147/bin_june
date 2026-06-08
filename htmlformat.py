#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from bs4 import BeautifulSoup
from dh import cprint, fsz, get_files


def process_file(path):
    content = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, parser="lxml.parser", features="lxml")
    before = len(content)
    new_content = soup.prettify()
    after = len(new_content)
    dsz = before - after
    print(f"{path.name}", end=" | ")
    if dsz:
        ratio = after / before * 100
        cprint(f"{fsz(dsz)} | {ratio:.1f}%", "cyan")
        path.write_text(new_content, encoding="utf-8")
        return
    else:
        cprint("no change", "grey")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".html", ".svg", ".xml", ".mhtml"])
    for f in files:
        process_file(f)
