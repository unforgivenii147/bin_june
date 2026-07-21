#!/data/data/com.termux/files/usr/bin/env python

"""Module for exsrt.py."""

from __future__ import annotations

import subprocess
import sys

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def main() -> None:
    input_file = sys.argv[1]
    output_file = input_file.replace(".mkv", ".srt")
    command = ["ffmpeg", "-i", input_file, "-map", "0:s:0", output_file]
    subprocess.run(command)


if __name__ == "__main__":
    main()
