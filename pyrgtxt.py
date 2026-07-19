#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import sys
from pathlib import Path

from joblib import Parallel, delayed

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def is_text_file(file_path):
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" not in chunk
    except (OSError, PermissionError):
        return False


def search_in_file(file_path, search_string):
    try:
        if not is_text_file(file_path):
            return []
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if search_string in content:
                return [str(file_path.relative_to(Path.cwd()))]
    except (OSError, PermissionError, UnicodeDecodeError):
        pass
    return []


def search_in_directory(directory, search_string, n_jobs=-1):
    files = [f for f in directory.rglob("*") if f.is_file()]
    results = Parallel(n_jobs=n_jobs)(delayed(search_in_file)(file, search_string) for file in files)
    matches = [match for sublist in results for match in sublist]
    return matches


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search_for.py <search_string>")
        sys.exit(1)
    search_string = sys.argv[1]
    current_dir = Path.cwd()
    print(f"Searching for '{search_string}' in text files under: {current_dir}")
    matches = search_in_directory(current_dir, search_string)
    if matches:
        print("\nFound in:")
        for match in matches:
            print(match)
    else:
        print("\nNo matches found.")
