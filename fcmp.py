#!/data/data/com.termux/files/usr/bin/env python


import sys
from filecmp import dircmp
from pathlib import Path
from pprint import pprint

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


if __name__ == "__main__":
    dir1 = Path.cwd()
    dir2 = Path(sys.argv[1])
    c = dircmp(dir1, dir2)
    pprint(c.report_full_closure())
