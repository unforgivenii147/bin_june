#!/data/data/com.termux/files/usr/bin/env python

import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path

from deep_translator import GoogleTranslator

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def translate_line(line: str) -> tuple[str, str] | None:
    if not line.strip():
        return None
    text = line.strip()
    try:
        translator = GoogleTranslator(source="fa", target="en")
        result = translator.translate(text)
        return (text, result)
    except Exception:
        return None


def translate_file(fname: str) -> None:
    path = Path(fname)

    with path.open("r", encoding="utf-8") as infile:
        linez = infile.readlines()

    outf = f"{path.stem}_eng{path.suffix}"
    outpath = path.parent / outf

    with Pool(cpu_count()) as pool:
        results = pool.imap_unordered(translate_line, linez)
        with outpath.open("w", encoding="utf-8") as f:
            for result in results:
                if result:
                    text, translated = result
                    print(f"{text} -> {translated}")
                    f.write(f"{text} = {translated}\n")


if __name__ == "__main__":
    translate_file(sys.argv[1])
