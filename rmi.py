from __future__ import annotations
import sys
from collections import deque
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
from dh import get_files, get_nobinary


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


INVISIBLE_CHARS = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\xa0",
    "\xad",
    "\ufeff",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
}


def clean_text(text: str) -> str:
    cleaned = ""
    for c in text:
        if ord(c) == 8204:
            continue
        if c == "\n":
            cleaned += c
            continue
        if c in INVISIBLE_CHARS:
            continue
        cleaned += c
    return cleaned


def process_file(path: Path) -> None:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    cleaned = clean_text(text)
    removed = len(text) - len(cleaned)
    if removed:
        print(f"{removed} invisible characters removed")
        path.write_text(cleaned, encoding="utf-8")
        return
    print("No invisible characters found")
    return


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_nobinary(cwd)
    for f in files:
        process_file(f)


if __name__ == "__main__":
    main()
