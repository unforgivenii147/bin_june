#!/data/data/com.termux/files/usr/bin/python

import shutil
import sys
from pathlib import Path


def main():
    paths = ["/sdcard", "/data/data/com.termux/files"]
    for cwd in paths:
        cdw = Path(cwd)
        nl = []
        for f in cdw.rglob("licenses"):
            if f.is_dir() and "dist-info" in str(f.parent):
                print(f)
                ans = input()
                if ans == "n":
                    sys.exit(0)
                shutil.rmtree(f)


if __name__ == "__main__":
    sys.exit(main())
