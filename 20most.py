#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import re
import sys
from collections import Counter, deque
from multiprocessing import Pool
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
from dh import get_nobinary


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


def extract_words(text: str):
    splt = text.strip().lower().replace("/", " ")
    return re.findall("[a-z]{3,}", splt)


def process_file(path: Path) -> None:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    words = extract_words(text)
    filtered = list(words)
    for word, _count in Counter(filtered).most_common(30):
        print(f"{word}", end=" ")


def main() -> None:
    args = sys.argv[1:]
    cwd = Path.cwd()
    files = [Path(arg) for arg in args] if args else get_nobinary(cwd)
    with Pool(8) as pool:
        pending = deque()
        for f in files:
            pending.append(pool.apply_async(process_file, (f,)))
            if len(pending) > 16:
                pending.popleft().get()
        while pending:
            pending.popleft().get()


if __name__ == "__main__":
    main()
