#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from dh import cprint, fsz, get_files, runcmd


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
    return Parallel(n_jobs=4)((delayed(process_function)(file_str, **kwargs) for file_str in file_strings))


def process_file(path) -> None:
    path = Path(path)
    before = path.stat().st_size
    _ret, _, _ = runcmd(["strip", str(path)], show_output=True)
    after = path.stat().st_size
    if not after:
        return
    dz = before - after
    if dz:
        cprint(f"{path.name} | ratio: {after / before:.1f}%")


if __name__ == "__main__":
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = (
        [Path(p) for p in args]
        if args
        else get_files(
            cwd,
            ext=[
                ".so",
                ".SO",
                ".so.1",
                ".so.0",
                ".so.2",
                ".so.2400",
                ".so.2400.0.0",
                ".so.0.0",
                ".so.0.1",
                ".so.1.0",
                ".so.0.0.0",
            ],
        )
    )
    mpf3(process_file, files)
    after = gsz(cwd)
    dsz = before - after
    if dsz:
        print(f"space freed: {fsz(dsz)}")
