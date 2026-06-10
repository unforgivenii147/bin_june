#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path


def process_file(path, text):
    content = path.read_text().lower()
    path = Path(path)
    target1 = "requires-dist: " + text
    if target1 in content:
        print(path.parent.name)


if __name__ == "__main__":
    cwd = Path("/data/data/com.termux/files/usr/lib/python3.13/site-packages")
    target = sys.argv[1]
    for path in cwd.rglob("METADATA"):
        process_file(path, target)
