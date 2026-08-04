#!/data/data/com.termux/files/usr/bin/python

from __future__ import annotations

import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

import cv2
import nude
from dh import cprint


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
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


nude_path = Path("nude")
nude_path.mkdir(exist_ok=True)
RESIZE = "-r" in sys.argv


def check_nude(path: str) -> bool:
    img = cv2.imread(path)
    h, w = img.shape[:2]
    n = nude.Nude(path)
    if (h > 800 or w > 800) and RESIZE:
        n.resize(maxheight=800, maxwidth=800)
    n.parse()
    del img, h, w
    print(n)
    return bool(n.result)


def process_file(path) -> None:
    path = Path(path)
    if "nude" in path.parts:
        return
    print(f"{path.name}")
    if check_nude(str(path)):
        cprint(f"{path.name} is nude", "cyan")
        new_path = nude_path / path.name
        path.rename(new_path)


if __name__ == "__main__":
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".jpg", ".jpeg", ".png", ".webp"])
    mpf3(process_file, files)
