#!/data/data/com.termux/files/usr/bin/env python

"""Module for heif2jpg.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pillow_heif as ph
from fastwalk import walk_files

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def process_file(path) -> bool:
    path = Path(path)
    if not path.exists():
        return False
    print(f"[OK] {path.name}")
    img = ph.open_heif(path)
    outfile = path.with_suffix(".jpg")
    img.save(outfile)
    return True


def main() -> None:
    cwd = Path().cwd()
    start_size = gsz(cwd)
    files = []
    for pth in walk_files(cwd):
        path = Path(pth)
        if path.is_file() and path.suffix in {".heif", ".heic"}:
            files.append(path)
    pool = Pool(8)
    pool.imap_unordered(process_file, files)
    pool.close()
    pool.join()
    after = gsz(cwd)
    print(f"{fornat_size(after - start_size)}")


if __name__ == "__main__":
    sys.exit(main())


def gsz(path):
    try:
        return Path(path).stat().st_size
    except Exception:
        return 0
