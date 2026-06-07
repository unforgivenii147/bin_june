#!/data/data/com.termux/files/usr/bin/python

import os
from pathlib import Path

EXCLUDE_DIRS = {".git"}
OUTPUT_FILE = "/sdcard/all2.txt"


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
            if Path(full).resolve() == Path(OUTPUT_FILE).resolve() or "license" not in str(fname).lower():
                continue
            yield full


def build_all_txt(root) -> None:
    files = list(collect_files(root))
    print(f"Found {len(files)} files")
    with Path(OUTPUT_FILE).open("w", encoding="utf-8") as out:
        for i, path in enumerate(files, 1):
            content = read_file(path)
            if content is None:
                print(f"Skipping unreadable file: {path}")
                continue
            out.write(content)
            if i != len(files):
                out.write("\n\n\n")
            print(f"Added: {path}")
    print(f"\nFinished: {OUTPUT_FILE} created.")


if __name__ == "__main__":
    build_all_txt(".")
