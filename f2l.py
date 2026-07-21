#!/data/data/com.termux/files/usr/bin/env python

"""Module for f2l.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def main() -> None:
    fn = sys.argv[1]
    filepath = Path(fn)
    with filepath.open(encoding="utf-8") as f:
        lines = [line.strip() for line in f]
    items = []
    for line in lines:
        quote_char = "'" if '"' in line else '"'
        items.append(f"{quote_char}{line}{quote_char}")
    formatted_content = "{" + ", ".join(items) + "}"
    filepath.write_text(formatted_content, encoding="utf-8")
    try:
        subprocess.run(["termux-clipboard-set"], input=formatted_content, text=True, capture_output=True)
        print(f"✓ Updated and copied: {filepath}")
    except FileNotFoundError:
        print(f"✓ File updated: {filepath}")
        print("⚠ Install termux-api for clipboard support")


if __name__ == "__main__":
    sys.exit(main())
