#!/data/data/com.termux/files/usr/bin/env python
from __future__ import annotations

import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageEnhance


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


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


def process_file(path):
    path = Path(path)
    try:
        with Image.open(path) as img:
            ce = ImageEnhance.Contrast(img)
            be = ImageEnhance.Brightness(img)
            se = ImageEnhance.Sharpness(img)
            cce = ImageEnhance.Color(img)
            img = ce.enhance(1.1)
            img = be.enhance(1.1)
            img = se.enhance(1.1)
            img = cce.enhance(1.1)
            img.save(path)
            print(f"Enhanced: {path.name}")
    except Exception as e:
        print(f"Error enhancing {path.name}: {e}")


def main():
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_files(p, ext=[".jpg", ".png", ".webp"]))
    else:
        files = get_files(cwd, ext=[".jpg", ".png", ".webp"])
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
