#!/data/data/com.termux/files/usr/bin/env python

"""Module for xlr.py."""

from __future__ import annotations

import sys
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def process_file(path: Path) -> None:
    path = Path(path)
    con = path.read_text()
    nl = [(line + "\n\n\n\n") for line in con.splitlines()]
    newconn = "\n".join(nl)
    path.write_text(newconn)


if __name__ == "__main__":
    fn = Path(sys.argv[1])
    process_file(fn)
