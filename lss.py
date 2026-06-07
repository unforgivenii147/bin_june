#!/data/data/com.termux/files/usr/bin/python

import os
import sys
from pathlib import Path


def main():
    cwd = Path.cwd()
    req = sys.argv[1].strip()
    found = [f for f in os.listdir(cwd) if f.startswith(req)]
    for k in found:
        print(k)


if __name__ == "__main__":
    main()
