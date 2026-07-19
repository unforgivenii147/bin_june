#!/data/data/com.termux/files/usr/bin/env python
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path


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


SIZE_THRESHOLD = 100
LINE_THRESHOLD = 3


def process_file(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    if path.stat().st_size < SIZE_THRESHOLD and len(path.read_text().splitlines()) < LINE_THRESHOLD:
        path.unlink()
        print(f"{path.name} removed")


def main() -> None:
    cwd = Path.cwd()
    files = get_files(cwd)
    for path in files:
        if not is_binary(path) and path.exists():
            process_file(path)
        else:
            print(f"{path.name} is binary")


if __name__ == "__main__":
    sys.exit(main())
