#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import sys
from pathlib import Path

from print_persian import print_persian as pp

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def ylines(path: Path):
    with path.open(encoding="utf-8") as f:
        yield from f


if __name__ == "__main__":
    fn = Path(sys.argv[1])
    for k in ylines(fn):
        print(pp(k))
