#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

if __name__ == "__main__":
    nl = []
    cwd = Path.cwd()
    for f in cwd.glob("*"):
        stm = f.stem
        if not f.is_file():
            continue
        if "-" in stm:
            indx = stm.index("-")
            nl.append(stm[:indx])
        else:
            nl.append(stm)
    for k in nl:
        print(k, end="   ")
