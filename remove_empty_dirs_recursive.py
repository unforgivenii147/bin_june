#!/data/data/com.termux/files/usr/bin/python

import os
from pathlib import Path


def main() -> None:
    count = 0
    for dirpath, dirnames, filenames in os.walk(Path.cwd(), topdown=False):
        if not dirnames and (not filenames):
            print(f"removing empty dir: {dirpath}")
            Path(dirpath).rmdir()
            count += 1
    print(f"total {count} empty dirs removed")


if __name__ == "__main__":
    main()
