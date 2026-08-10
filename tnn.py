#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import sys
from pathlib import Path

from dh import cprint, get_nobinary, mpf3

CHUNK_SIZE = 1024 * 1024


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


def process_file(path: str | Path) -> None:
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    new_content = content.replace("\t", "    ")
    if new_content == content:
        cprint(f"{path.name} (no change)", "grey")
        return
    path.write_text(new_content, encoding="utf-8")
    cprint(f"{path.name} (updated)", "cyan")


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_nobinary(p))
    else:
        files = get_nobinary(cwd)
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
