#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import sys
from multiprocessing import get_context
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def mpf3(func, files):
    p = get_context("spawn").Pool(8)
    for f in files:
        p.apply_async(func, (f,))
    p.close()
    p.join()


def unique_path(path: Path | str) -> Path:
    path = Path(path)
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


def process_file(path) -> None:
    path = Path(path)
    if not path.exists():
        path = Path(str(path).lower())
        if not path.exists():
            return
    new_name = path.name.lower()
    if new_name == path.name:
        return
    new_path = path.with_name(new_name)
    if new_path.exists():
        new_path = unique_path(new_path)
    path.rename(new_path)
    print(f"{path.name} -> {new_path.name}")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = (
        list(cwd.glob("*")) if not args else [p for p in cwd.rglob("*") if ".git" not in p.parts and not p.is_symlink()]
    )
    mpf3(process_file, files)
