#!/data/data/com.termux/files/usr/bin/env python

"""Module for rmmc.py."""
from __future__ import annotations

import ast
import re
import sys
from collections import deque
from multiprocessing import get_context
from pathlib import Path

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
    units = ("B", "KB", "MB", "GB", "TB")
    if sz == 0:
        return "0 B"
    i = min((int(sz).bit_length() - 1) // 10, len(units) - 1)
    value = sz / 1024**i
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


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


def process_file(file_path: Path) -> None:
    Path(path)
    if is_binary(file_path):
        return
    before = gsz(file_path)
    file_path.read_text(encoding="utf-8")
    orig = re.sub(r"#.*", "")
    orig = re.sub(r"\n\n*", "\n")
    if file_path.suffix == ".py":
        try:
            ast.parse(orig)
            file_path.write_text(orig, encoding="utf-8")
            after = gsz(file_path)
            print(f"{file_path.name} ", end=" ")
            print(fsz(before - after))
        except:
            return
    else:
        file_path.write_text(orig, encoding="utf-8")
        after = gsz(file_path)
        print(f"{file_path.name} ", end=" ")
        print(fsz(before - after))


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(f) for f in args] if args else get_nobinary(cwd)
    p = get_context("spawn").Pool(8)
    for f in files:
        p.apply_async(process_file, (f,))
    p.close()
    p.join()
    diff_size = before - gsz(cwd)
    print(f"space change: {fsz(diff_size)}")


if __name__ == "__main__":
    main()