#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

if __name__ == "__main__":
    fn = sys.argv[1]
    newlines = []
    str_to_add = sys.argv[2]
    with Path(fn).open("r") as f:
        for line in f:
            ln = str_to_add + " " + line
            newlines.append(ln)
    with Path(fn).open("w") as fo:
        fo.writelines(newlines)
    print(f"{fn} updated")
