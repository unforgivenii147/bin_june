#!/data/data/com.termux/files/usr/bin/env python


import sys
from os import scandir as os_scandir
from pathlib import Path

import cv2

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def process_file(path) -> None:
    path_str = str(path)
    img = cv2.imread(path_str)
    if not img.any():
        return
    h, w = img.shape[:2]
    if 1 < w < 200:
        FACTOR = 8
    elif 200 <= w <= 500:
        FACTOR = 6
    elif 500 <= w <= 1000:
        FACTOR = 4
    elif 1000 <= w <= 2000:
        FACTOR = 2
    elif w > 2000:
        del w, h, img
        return
    print(f"[✓] {path.name}:{h}X{w} -> {h * FACTOR}X{w * FACTOR}")
    try:
        resized = cv2.resize(img, (w * FACTOR, h * FACTOR), interpolation=cv2.INTER_LANCZOS4)
        del img, h, w
        sharpened = cv2.addWeighted(resized, 1.5, resized, -0.5, 0)
        del resized
        cv2.imwrite(path, sharpened)
        del sharpened
        return
    except:
        return


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".webp", ".jpg", ".jpeg", ".png"])
    c = 0
    for f in files:
        c += 1
        print(f"{c}/{len(files)}")
        process_file(f)
