#!/data/data/com.termux/files/usr/bin/env python

"""Module for tell_font_name.py."""

from __future__ import annotations

import re
import sys
from collections import deque
from collections.abc import Callable, Iterable
from multiprocessing import get_context
from pathlib import Path
from typing import Any

from fontTools.ttLib import TTFont
from fontTools.ttLib.ttFont import TTFont
from termcolor import cprint


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


def mpf_async(func: Callable[[Any], Any], items: Iterable[Any]):
    with get_context("spawn").Pool(MAX_WORKERS) as p:
        async_results = [p.apply_async(func, (item,)) for item in items]
        results = []
        for i, async_result in enumerate(async_results):
            try:
                results.append(async_result.get(timeout=30))
            except Exception as e:
                print(f"Item {i} failed: {e}")
                results.append(None)
        return results


mpf = mpf_async


def is_ascii_printable(s: str) -> bool:
    return all(32 <= ord(c) <= 126 for c in s)


def clean_filename(s: str) -> str:
    s = re.sub(r"[^\w\\-\.]", "", s)
    return s.strip("_-.")


def get_best_name(font: TTFont, name_id: int):
    fallback = None
    for rec in font["name"].names:
        if rec.nameID != name_id:
            continue
        try:
            name = rec.toUnicode().strip()
        except Exception:
            continue
        if rec.platformID == 3 and rec.langID == 1033:
            return name
        if is_ascii_printable(name):
            fallback = name
    return fallback


def get_font_names(path) -> tuple[str, str] | tuple[None, None]:
    font = TTFont(path)
    family = get_best_name(font, 1)
    subfamily = get_best_name(font, 2)
    if not family:
        return (None, None)
    family = clean_filename(family)
    subfamily = "Regular" if not subfamily else clean_filename(subfamily)
    if subfamily.lower() == family.lower():
        subfamily = "Regular"
    return (family, subfamily)


def process_file(fn: Path) -> int:
    Path(path)
    try:
        family, style = get_font_names(fn)
    except Exception as e:
        cprint(f"error: {e}", "magenta")
        return 1
    if not family:
        cprint("name not found", "magenta")
        return 1
    ext = fn.suffix.lower()
    new_path = fn.parent / f"{family}-{style}{ext}"
    if fn.name == new_path.name:
        cprint("no change", "blue")
        return 0
    new_path = Path(
        str(new_path)
        .replace("_1", "")
        .replace("_2", "")
        .replace("_3", "")
        .replace("_4", "")
        .replace("_5", "")
        .replace("_6", "")
        .replace("_7", "")
        .replace("_8", "")
        .replace("_9", "")
    )
    if new_path.exists():
        new_path = unique_path(new_path)
    fn.rename(new_path)
    cprint(f"{new_path.name}", "green")
    return 0


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = (
        [Path(arg) for arg in args]
        if args
        else get_files(cwd, extensions=[".ttf", ".woff", ".woff2", ".bin", ".otf", ".eot"])
    )
    if not files:
        print("no files found")
        return
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    _ = mpf(process_file, files)


if __name__ == "__main__":
    main()
