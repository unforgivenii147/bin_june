#!/data/data/com.termux/files/usr/bin/python

import hashlib
import os
import sys
from pathlib import Path


def file_hash(path, block_size=65536):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while chunk := f.read(block_size):
            h.update(chunk)
    return h.hexdigest()


def build_hash_map(root):
    hash_map = {}
    for base, _dirs, files in os.walk(root):
        for f in files:
            full = os.path.join(base, f)
            rel = os.path.relpath(full, root)
            hash_map[rel] = file_hash(full)
    return hash_map


def compare_dirs(dir1, dir2):
    map1 = build_hash_map(dir1)
    map2 = build_hash_map(dir2)
    changed = []
    common = []
    only_in_dir1 = []
    for rel_path, h1 in map1.items():
        if rel_path not in map2:
            only_in_dir1.append(rel_path)
        elif h1 == map2[rel_path]:
            common.append(rel_path)
        else:
            changed.append(rel_path)
    Path("dir1.txt").write_text("\n".join(changed), encoding="utf-8")
    Path("common.txt").write_text("\n".join(common), encoding="utf-8")
    Path("only_in_dir1.txt").write_text("\n".join(only_in_dir1), encoding="utf-8")


if __name__ == "__main__":
    DIR1 = sys.argv[1]
    DIR2 = sys.argv[2]
    compare_dirs(DIR1, DIR2)
    print("Comparison complete. See dir1.txt, common.txt, only_in_dir1.txt")
