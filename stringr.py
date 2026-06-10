#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import get_files, is_binary, mpf3, runcmd

cwd = Path.cwd()
outfile = cwd / "all_strings.txt"
all_files = 0
c = 0


def process_file(fp):
    global all_files
    path = Path(path)
    global c
    c += 1
    print(f"[{c}/{all_files}] {fp.name}")
    if not fp.exists() or not is_binary(fp):
        return
    _, txt, _ = runcmd(["strings", str(fp)], show_output=False)
    with outfile.open("a", encoding="utf-8") as f:
        f.write(f"\n# filename : {fp.name}\n{txt}")
    return


def main():
    args = sys.argv[1:]
    global all_files
    files = [Path(arg) for arg in args] if args else get_files(cwd)
    all_files = len(files)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
