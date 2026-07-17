#!/data/data/com.termux/files/usr/bin/env python
import sys
from collections import deque
from pathlib import Path

import cv2


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
