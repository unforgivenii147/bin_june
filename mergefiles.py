#!/data/data/com.termux/files/usr/bin/python

import os
from pathlib import Path

from dh import get_random_filename

EXCLUDE_DIRS = {".git"}
OUTPUT_FILE = get_random_filename(8) + ".txt"


def read_file(path):
    try:
        with Path(path).open(encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None


def collect_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            if Path(full).resolve() == Path(OUTPUT_FILE).resolve() or fname == Path(__file__).name:
                continue
            yield full


def merge_files(root):
    files = list(collect_files(root))
    with Path(OUTPUT_FILE).open("w", encoding="utf-8") as fo:
        for i, path in enumerate(files, 1):
            content = read_file(path)
            if content is None:
                continue
            fo.write(content)
            if i != len(files):
                fo.write("\n")
    print(f"\nsaved as: {OUTPUT_FILE}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Merge files recursively into merged.txt")
    ap.add_argument("--path", default=".", help="Directory to scan")
    args = ap.parse_args()
    merge_files(args.path)
