#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path
from print_persian import print_persian as pp


def ylines(fp: Path):
    with fp.open(encoding="utf-8") as f:
        for line in f:
            yield line


if __name__ == "__main__":
    fn = Path(sys.argv[1])
    for k in ylines(fn):
        print(pp(k))
