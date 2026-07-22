#!/data/data/com.termux/files/usr/bin/env python

"""Module for find_empty.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def main() -> None:
    cwd = Path.cwd()
    for r, _, files in os.walk(cwd):
        for f in files:
            if f.startswith("__init__.py") or f.endswith("py.typed"):
                continue
            path = Path(r) / f
            if path.is_symlink():
                continue
            if path.is_file() and not path.stat().st_size:
                print(path.relative_to(cwd))


if __name__ == "__main__":
    sys.exit(main())
