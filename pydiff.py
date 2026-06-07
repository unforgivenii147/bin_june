#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import cprint, read_lines


def process_files(fp1, fp2):
    lines1 = read_lines(fp1)
    lines2 = read_lines(fp2)
    only_in_first = [p for p in lines1 if p not in lines2]
    only_in_second = [p for p in lines2 if p not in lines1]
    common_lines = [p for p in lines1 if p in lines2]
    if only_in_first:
        cprint(f"only in {fp1.name} :", "cyan")
        for line in only_in_first:
            cprint(f"  - {line}", "green")
    if only_in_second:
        cprint(f"only in {fp2.name} :", "cyan")
        for line in only_in_second:
            cprint(f"  - {line}", "yellow")
    cprint(
        f"common lines: {len(common_lines)}\nonly in {fp1.name}: {len(only_in_first)}\nonly in {fp2.name}: {len(only_in_second)}",
        "blue",
    )


if __name__ == "__main__":
    f1 = Path(sys.argv[1])
    f2 = Path(sys.argv[2])
    process_files(f1, f2)
