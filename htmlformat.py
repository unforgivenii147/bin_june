#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path
from bs4 import BeautifulSoup
from dh import get_files, gsz, rrs, mpf3


def process_file(path) -> None:
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, parser="lxml.parser", features="lxml")
    before = gsz(path)
    new_content = soup.prettify()
    after = len(new_content)
    rrs(path, before, after)


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".html", ".htm", ".xhtml"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    mpf3(process_file, files)
