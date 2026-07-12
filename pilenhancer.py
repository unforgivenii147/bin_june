#!/data/data/com.termux/files/usr/bin/env python


import sys
from collections.abc import Callable, Iterable
from os import scandir as os_scandir
from pathlib import Path

from PIL import Image, ImageEnhance

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


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
