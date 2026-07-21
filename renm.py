#!/data/data/com.termux/files/usr/bin/env python

"""Module for renm.py."""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from deep_translator import GoogleTranslator
from fastwalk import walk_files
from tqdm import tqdm

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


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

    clean_name = re_sub(r"(_\d+)+", "", path.name)
    return path.with_name(clean_name)


DIRECTORY = "."
non_english_pattern = re.compile(r"[^\x00-\x7F]")


def is_english(text: str) -> bool:
    return not non_english_pattern.search(text)


translation_cache = {}


def translate_name(name):
    base, ext = os.path.splitext(name)
    if is_english(base):
        return name, name
    if base in translation_cache:
        return name, translation_cache[base] + ext
    try:
        translated = GoogleTranslator(source="auto", target="en").translate(base)
        translation_cache[base] = translated
        return name, translated + ext
    except Exception:
        return name, name


def rename_files(directory: str) -> None:
    paths = [Path(p) for p in walk_files(directory)]
    unique_names_to_translate = list({p.name for p in paths if not is_english(p.name)})
    translation_map = {}
    with ThreadPoolExecutor(8) as executor:
        futures = [executor.submit(translate_name, name) for name in unique_names_to_translate]
        for future in tqdm(
            as_completed(futures),
            total=len(unique_names_to_translate),
            desc="Translating filenames",
        ):
            original, translated = future.result()
            translation_map[original] = translated
    for path in sorted(paths, key=lambda x: len(x.parts), reverse=True):
        if path.name not in translation_map:
            continue
        new_name = translation_map[path.name]
        if new_name == path.name:
            continue
        new_path = path.with_name(new_name)
        new_path = unique_path(new_path)
        try:
            Path(path).rename(new_path)
            print(f"Renamed: {path.name} -> {new_path.name}")
        except OSError as e:
            print(f"Error renaming {path.name}: {e}")


if __name__ == "__main__":
    rename_files(DIRECTORY)
