#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import sys

from googlesearch import search

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

if __name__ == "__main__":
    tts = sys.argv[1]
    for result in search(tts):
        print(result)
