#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import json
import os
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

import xmltodict
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


MAX_QUEUE = 16
REMOVE_ORIG = True


def process_file(path) -> None:
    path = Path(path)
    try:
        jsonpath = path.with_suffix(".json")
        cprint(f"{jsonpath} created.", "cyan")
        xml_content = path.read_text(encoding="utf-8", errors="ignore")
        with jsonpath.open("w") as f:
            data = xmltodict.parse(xml_content)
            json.dump(data, f, ensure_ascii=False, indent=2)
        if path.suffix == ".xml" and REMOVE_ORIG:
            path.unlink()
    except OSError as e:
        print(f"error {e}")


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".xml", ".svg"])
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
