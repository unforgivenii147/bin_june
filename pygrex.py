#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import re
import sys

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

if len(sys.argv) != 2:
    print("Usage: python script.py <filename>")
    sys.exit(1)
filename = sys.argv[1]
with open(filename, encoding="utf-8") as f:
    lines = [line.rstrip("\n") for line in f]
pattern = "^(?:{})$".format("|".join(re.escape(line) for line in lines))
print(pattern)
