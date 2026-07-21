#!/data/data/com.termux/files/usr/bin/env python

"""Module for cpprun.py."""

from __future__ import annotations

import sys

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        for arg in args:
            if "*" in arg:
                p = glob_glob(arg)
                print(p)
