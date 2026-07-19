#!/data/data/com.termux/files/usr/bin/env python
from __future__ import annotations

import os
import sys
from collections import deque
from pathlib import Path

from ascii_magic import AsciiArt


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


def process_file(image_path: Path) -> None:
    path = Path(path)
    art = AsciiArt.from_image(image_path)
    art.to_terminal(columns=os.get_terminal_size().columns, width_ratio=2, monochrome=False)


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(arg) for arg in args] if args else get_files(cwd, ext=[".jpg", ".png", ".bmp", ".webp"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    pool = Pool(8)
    for _ in pool.imap_unordered(process_file, files):
        pass
    pool.close()
    pool.join()


if __name__ == "__main__":
    main()
