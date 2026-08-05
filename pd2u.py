#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from pathlib import Path
from dh.fileutils import is_binary

CHUNK_SIZE = 65536
BINARY_BYTES = bytes(range(9)) + bytes([11, 12]) + bytes(range(14, 32))


def dos2unix_file(path: Path) -> None:
    data = path.read_text()
    new_data = data.replace("\n\r", "\n")
    path.write_text(new_data)


if __name__ == "__main__":
    import sys

    fn = Path(sys.argv[1])
    if not is_binary(fn):
        dos2unix_file(fn)
