#!/data/data/com.termux/files/usr/bin/env python

"""Module for tfa.py."""

from __future__ import annotations

import json
from pathlib import Path

from deep_translator import GoogleTranslator

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

INPUT_FILE = "words.txt"
OUTPUT_FILE = "dic.json"


def translate_word(word: str) -> str | None:
    try:
        return GoogleTranslator(source="auto", target="en").translate(word)
    except Exception as e:
        print(f"Error translating '{word}': {e}")
        return None


def main() -> None:
    translations = {}
    with Path(INPUT_FILE).open(encoding="utf-8") as f:
        words = [line.strip() for line in f if line.strip()]
    print(f"Loaded {len(words)} Persian words")
    for w in words:
        eng = translate_word(w)
        if eng:
            translations[w] = eng
            print(f"{w} → {eng}")
    with Path(OUTPUT_FILE).open("w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)
    print(f"\nSaved JSON dictionary to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
