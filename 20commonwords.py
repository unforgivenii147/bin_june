#!/data/data/com.termux/files/usr/bin/env python


import re
import sys
from collections import Counter
from pathlib import Path

import regex as re

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


USER_STOPWORDS_FILE = Path("/sdcard/stopwords")


def load_user_stopwords(path: Path):
    if not path.is_file():
        return set()
    stopwords = set()
    with path.open(errors="ignore") as f:
        for line in f:
            line = line.strip().lower()
            if not line or line.startswith("#"):
                continue
            stopwords.add(line)
    return stopwords


EXCLUDE = load_user_stopwords(USER_STOPWORDS_FILE)


def extract_words(text: str):
    return re.findall(r"[a-z]{3,}", text.lower())


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <file>")
        sys.exit(1)
    src = sys.argv[1]
    try:
        text = Path(src).read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        print("File not found")
        sys.exit(1)
    words = extract_words(text)
    filtered = [w for w in words if w not in EXCLUDE]
    dst = ""
    for word, count in Counter(filtered).most_common(50):
        dst = dst + str(word) if count == 5 else dst + str(word) + "_"
        print(f"{word:<15} {count}")
    p = Path(src)
    dst = Path(str(dst)[:25] + p.suffix)
    dst = unique_path(dst)


if __name__ == "__main__":
    main()
