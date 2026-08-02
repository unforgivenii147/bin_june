#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import json
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


def process_file(path) -> None:
    path = Path(path)
    before = gsz(path)
    data = path.read_text(encoding="utf-8")
    if not before:
        del data, before
        print(f"{path.name}  | (no change)")
        return
    try:
        jdata = json.loads(data)
        with path.open("w", encoding="utf8") as fo:
            json.dump(jdata, fo, ensure_ascii=False, indent=2)
        after = gsz(path)
        diffsize = abs(after - before)
        print(f"{path.name}", end=" | ")
        if not diffsize:
            cprint("(no change)", "grey")
            return
        ratio = diffsize / after * 100
        ratio2 = abs(before - after) / before * 100
        cprint(f"{ratio:.2f}% | {ratio2:.2f}%", "cyan")
        return
    except:
        cprint(f"{path.name} Error", "yellow")
        return


if __name__ == "__main__":
    cwd = Path.cwd()
    before = gsz(cwd)
    files = get_files(cwd, ext=[".json"])
    if not files:
        print("no json files found")
        sys.exit(1)
    print(f"{len(files)} json files found.")
    mpf3(process_file, files)
    after = gsz(cwd)
    dsz = abs(before - after)
    if not dsz:
        sys.exit(1)
    ratio = dsz / before * 100
    cprint(f"space change: {fsz(dsz)} {ratio:.2f}%")
