#!/data/data/com.termux/files/usr/bin/env python
from __future__ import annotations

import os
import sys

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def sort_and_dedup(file_name: str) -> None:
    file_size = os.path.getsize(file_name)
    with open(file_name) as f:
        lines = f.readlines()
    unique_lines = sorted(set(lines))
    removed_lines = set(lines) - set(unique_lines)
    with open(file_name, "w") as f:
        f.writelines(unique_lines)
    if removed_lines:
        print(f"Removed {len(removed_lines)} lines.")
        print("Removed lines:")
        for line in sorted(set(removed_lines)):
            print(line.strip())
    else:
        print("no change")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sort_uniq.py <file_name> [-d]")
        sys.exit(1)
    file_name = sys.argv[1]
    sort_and_dedup(file_name)
