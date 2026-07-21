#!/data/data/com.termux/files/usr/bin/env python

"""Module for cleanhistory.py."""

from __future__ import annotations

from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

if __name__ == "__main__":
    fn = Path.home() / ".bash_history"
    nl = []
    with fn.open(encoding="utf-8") as f:
        nl.extend(line for line in f if 'cd "`printf' not in line)
    nl = list(set(nl))
    with fn.open("w", encoding="utf-8") as fo:
        fo.writelines(nl)
    print("done.")
