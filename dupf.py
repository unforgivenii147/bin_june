#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from xxhash import xxh64
from dh import cprint

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = "B", "KB", "MB", "GB", "TB"
    if sz == 0:
        return "0 B"
    i = min((int(sz).bit_length() - 1) // 10, len(units) - 1)
    value = sz / 1024**i
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


CHUNKSIZE = 32768


def should_skip(path: Path) -> bool:
    path = Path(path)
    return bool(
        path.is_symlink()
        or not path.stat().st_size
        or any(pat in path.parts for pat in (".git", "__pycache__", ".mypy_cache", ".ruff_cache"))
    )


def get_hash_file(path):
    if not path.exists() or not path.stat().st_size:
        return "", path
    h = xxh64()
    try:
        with path.open("rb") as f:
            while chunk := f.read(CHUNKSIZE):
                h.update(chunk)
        return h.hexdigest(), path
    except OSError:
        return "", path


def find_duplicates() -> None:
    cwd = Path.cwd()
    files_by_hash = defaultdict(list)
    duplicate_count = 0
    ptp = [path for path in cwd.rglob("*") if path.is_file() and not should_skip(path)]
    files_by_size = {}
    for p in ptp:
        try:
            size = p.stat().st_size
            files_by_size.setdefault(size, []).append(p)
        except OSError as e:
            print(f"Error getting size for {p}: {e}")
            continue
    paths_to_hash = []
    for size, paths in files_by_size.items():
        if len(paths) > 1:
            paths_to_hash.extend(paths)
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_path = {executor.submit(get_hash_file, path): path for path in paths_to_hash}
        for future in as_completed(future_to_path):
            hash_result, path = future.result()
            if hash_result is not None:
                files_by_hash.setdefault(hash_result, []).append(path)
    total = 0
    for hash, paths in files_by_hash.items():
        if len(paths) > 1:
            duplicate_count += len(paths) - 1
            print(f"hash {hash} :")
            for file_path in paths:
                relative_path = file_path.relative_to(cwd)
                cprint(f" - {relative_path}", "cyan")
                total += gsz(file_path)
    if total:
        cprint(f"total : {fsz(total)}")
    else:
        cprint(f"NO DUPS")


if __name__ == "__main__":
    find_duplicates()
