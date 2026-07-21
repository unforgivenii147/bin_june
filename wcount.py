#!/data/data/com.termux/files/usr/bin/env python

"""Module for wcount.py."""
from __future__ import annotations

import json
import sys
from collections import deque
from multiprocessing import get_context
from pathlib import Path

from toolz import compose, frequencies
from toolz.curried import map as _map

CHUNK_SIZE = 1024 * 1024


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


def is_binary(path: Path | str) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > 0.3
    except Exception:
        return True


def get_nobinary(path: str | Path) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


MAX_QUEUE = 8


def stem(word):
    return word.lower().rstrip(",.|;:'\"").lstrip("'\"")


def process_file(path):
    path = Path(path)
    if path.is_symlink():
        print(f"skipping symlink {path.name}")
    print(f"{path.name}")
    word_count = compose(frequencies, _map(stem), str.split)
    content = path.read_text(encoding="utf-8")
    return word_count(content)


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(f) for f in args] if args else get_nobinary(cwd)
    results = {}
    with get_context("spawn").Pool(8) as pool:
        pending = deque()
        for f in files:
            pending.append(pool.apply_async(process_file, (f,)))
            if len(pending) > MAX_QUEUE:
                result = pending.popleft().get()
                for x in result:
                    if x not in results:
                        results[x] = result.get(x)
                    else:
                        results[x] += result.get(x)
        while pending:
            result = pending.popleft().get()
            for x in result:
                if x not in results:
                    results[x] = result.get(x)
                else:
                    results[x] += result.get(x)
    outfile = Path("word_count.json")
    wsorted = [results.get(key) for key in results]
    wsorted = sorted(wsorted, reverse=True)
    word_sorted = {}
    for item in wsorted:
        word_sorted[item] = results.get(item)
    with Path(outfile).open("w", encoding="utf-8") as fo:
        json.dump(word_sorted, fo, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()