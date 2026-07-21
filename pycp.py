#!/data/data/com.termux/files/usr/bin/env python

"""Module for pycp.py."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

src = Path(sys.argv[1].strip())
dest = Path("/data/data/com.termux/files/usr")
shutil.copy2(str(src), dest)
print("done")
