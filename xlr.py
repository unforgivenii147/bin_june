#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path


def process_file(path):
    con = path.read_text()
    nl = [line + "\n\n\n\n" for line in con.splitlines()]
    newconn = "\n".join(nl)
    path.write_text(newconn)


if __name__ == "__main__":
    fn = Path(sys.argv[1])
    process_file(fn)
