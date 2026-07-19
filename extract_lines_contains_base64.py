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


def get_nobinary(path: str | Path) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


def process_file(path: Path) -> None:
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    nl = []
    found = 0
    for line in lines:
        if "base64," in line:
            found += 1
            indx = line.index("base64,") + 7
            cleaned = line[indx:]
            if '"' in cleaned:
                end_indx = cleaned.index('"')
                cleaned = cleaned[:end_indx]
            if " " in cleaned:
                end_indx = cleaned.index(" ")
                cleaned = cleaned[:end_indx]
            if ")" in cleaned:
                end_indx = cleaned.index(")")
                cleaned = cleaned[:end_indx]
            nl.append(cleaned)
    if found:
        print(f"{path.name} : {found}")
        with Path("b64").open("a", encoding="utf-8") as f:
            f.write("\n")
            f.writelines(f"{k}\n" for k in nl)


def main() -> None:
    args = sys.argv[1:]
    cwd = Path.cwd()
    files = [Path(arg) for arg in args] if args else get_nobinary(cwd)
    for f in files:
        process_file(f)


if __name__ == "__main__":
    sys.exit(main())
