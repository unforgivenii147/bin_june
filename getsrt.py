#!/data/data/com.termux/files/usr/bin/env python

"""Module for getsrt.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def extract_subtitles(path) -> None:
    if not path.exists():
        return
    output_path = path.with_suffix(".srt")
    cmd = ["ffmpeg", "-i", str(path), "-map", "0:s:0", "-y", str(output_path)]
    try:
        subprocess.run(cmd, check=True)
    except:
        print("Error")


if __name__ == "__main__":
    fn = Path(sys.argv[1].strip())
    extract_subtitles(fn)
