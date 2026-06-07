#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path


def main():
    fn = sys.argv[1]
    lines = []
    with Path(fn).open(encoding="utf-8") as f:
        lines = f.readlines()
    new_fn = Path(fn).stem + "_list.txt"
    with Path(new_fn).open("w", encoding="utf-8") as fo:
        fo.write("{")
        for line in lines:
            str1 = '"' + str(line.strip()) + '", ' if '"' not in line else "'" + str(line.strip()) + "', "
            fo.write(str1)
        fo.write("}")


if __name__ == "__main__":
    sys.exit(main())
