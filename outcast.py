#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

from pathlib import Path
from dh.fileutils import get_random_filename


def copy_largest_file(source_dir, dest):
    largest = None
    max = -1
    for path in source_dir.iterdir():
        if path.is_file():
            size = path.stat().st_size
            if size > max:
                max = size
                largest = path
    if largest:
        dest.write_bytes(largest.read_bytes())
        print(f"{dest.name} ({max / (1024 * 1024)} MB)")


if __name__ == "__main__":
    source = Path("/sdcard/Android/data/org.telegram.messenger/cache")
    dest = Path(f"/sdcard/Download/{get_random_filename()}.mkv")
    copy_largest_file(source, dest)
