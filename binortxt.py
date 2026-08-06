#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
CHUNK_SIZE = 1024 * 1024
from dh import get_files, mpf3
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
        nontext = sum((1 for b in chunk if b not in text_chars))
        return nontext / len(chunk) > 0.3
    except Exception:
        return True
cwd = Path.cwd()
bin_dir = Path(f"{cwd}/binary")
bin_dir.mkdir(exist_ok=True)
def process_file(path) -> None:
    path = Path(path)
    if is_binary(path):
        newpath = bin_dir / path.name
        path.rename(newpath)
def main() -> None:
    files = get_files(cwd)
    mpf3(process_file, files)
if __name__ == "__main__":
    sys.exit(main())
