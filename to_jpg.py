#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import os
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
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


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = ("B", "KB", "MB", "GB", "TB")
    if sz == 0:
        return "0 B"
    i = min((int(sz).bit_length() - 1) // 10, len(units) - 1)
    value = sz / 1024**i
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


def rrs(path, before, after) -> None:
    delta = before - after
    msg = (
        "\x1b[5;92mNO CHANGE\x1b[0m"
        if delta == 0
        else f"\x1b[5;92m{('-' if delta > 0 else '+')} \x1b[5;94m{fsz(abs(delta))}\x1b[0m | \x1b[5;96m{after / before * 100:.1f}\x1b[5;95m%\x1b[0m"
    )
    print(f"\n{path.name} | {msg}")


def unique_path(path: Path | str) -> Path:
    path = _clean_fname(Path(path))
    if not path.exists():
        return path
    parent = path.parent
    suffixes = path.suffixes
    if suffixes:
        first_suffix_index = path.name.find(suffixes[0])
        stem = path.name[:first_suffix_index]
        full_suffix = "".join(suffixes)
    else:
        stem = path.name
        full_suffix = ""
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{full_suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def _clean_fname(path: Path) -> Path:
    from re import sub as re_sub

    clean_name = re_sub("(_\\d+)+", "", path.name)
    return path.with_name(clean_name)


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


try:
    import cv2
    import numpy as np

    USE_CV2 = True
except ImportError:
    from PIL import Image

    USE_CV2 = False


def process_file(path):
    path = Path(path)
    if not path.is_file():
        print(f"Skipping: {path.name} (Unsupported format or not a file)")
        return
    if path.suffix.lower() == ".jpg":
        return
    output_path = path.with_suffix(".jpg")
    if output_path.exists():
        output_path = unique_path(output_path)
    before = gsz(path)
    try:
        if USE_CV2:
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is None:
                print(f"Error: Could not decode {path.name}")
                return
            if img.shape[2] == 4:
                b, g, r, a = cv2.split(img)
                white_bg = np.full(img.shape[:2], 255, dtype=np.uint8)
                alpha = a.astype(float) / 255.0
                img_b = (b.astype(float) * alpha + white_bg.astype(float) * (1 - alpha)).astype(np.uint8)
                img_g = (g.astype(float) * alpha + white_bg.astype(float) * (1 - alpha)).astype(np.uint8)
                img_r = (r.astype(float) * alpha + white_bg.astype(float) * (1 - alpha)).astype(np.uint8)
                final_img = cv2.merge((img_b, img_g, img_r))
            else:
                final_img = img
            success = cv2.imwrite(str(output_path), final_img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        else:
            img = Image.open(path)
            if img.mode in {"RGBA", "LA"}:
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                final_img = background
            else:
                final_img = img
            final_img.save(output_path, "JPEG", quality=95)
            success = True
        if success:
            path.unlink()
            after = gsz(output_path)
            rrs(path, before, after)
            return
        return
    except Exception:
        return


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(f) for f in args] if args else get_files(cwd, ext=[".webp", ".bmp", ".jpeg", ".png", ".tiff", "PNG"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)
    diffsize = before - gsz(cwd)
    cprint(f"space freed: {fsz(diffsize)}")


if __name__ == "__main__":
    main()
