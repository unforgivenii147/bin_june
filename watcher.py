#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

from watchfiles import watch

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

if __name__ == "__main__":
    for changes in watch("."):
        print(changes)
