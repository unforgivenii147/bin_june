#!/data/data/com.termux/files/usr/bin/env python


from __future__ import annotations

import sys
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

CHUNK_SIZE = 65536
BINARY_BYTES = bytes(range(0, 9)) + bytes([11, 12]) + bytes(range(14, 32))


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        return any(b in BINARY_BYTES for b in chunk)
    except Exception:
        return True


def dos2unix_file(path: Path) -> None:
    data = path.read_text()
    new_data = data.replace("\n\r", "\n")
    path.write_text(new_data)


if __name__ == "__main__":
    import sys

    fn = Path(sys.argv[1])
    if not is_binary(fn):
        dos2unix_file(fn)
