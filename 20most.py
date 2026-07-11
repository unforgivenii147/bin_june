#!/data/data/com.termux/files/usr/bin/env python


import re
import sys
from collections import Counter, deque
from multiprocessing import Pool
from pathlib import Path
from dh import get_nobinary


def extract_words(text: str):
    splt = text.strip().lower().replace("/", " ")
    return re.findall(r"[a-z]{3,}", splt)


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
