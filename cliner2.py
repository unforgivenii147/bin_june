#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import re
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

LOG_EXT = ".log"
PATTERNS = [
    "\\^\\[",
    "\\[[\\dA-Z;]+m",
    "\\[\\d+[A-Z]",
    "\\[[\\dA-Z;]+",
    "\\^M",
    "\\(B",
    "\\(0",
    "\\x1b\\[[0-9;]*[A-Za-z]",
    "\\x1b\\([0-9AB]",
    "\\r",
    "\\x0f",
    "\\x0e",
]


def clean_line(line: str) -> str:
    cleaned = line
    for pattern in PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)
    return re.sub(r" {2,}", " ", cleaned)


def clean_file(file_path: Path) -> None:
    try:
        with Path(file_path).open(encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        cleaned_lines = [clean_line(line) for line in lines]
        with Path(file_path).open("w", encoding="utf-8") as f:
            f.writelines(cleaned_lines)
        print(f"✓ Cleaned: {file_path}")
    except Exception as e:
        print(f"✗ Error processing {file_path}: {e}")


def main() -> None:
    cwd = Path.cwd()
    log_files = list(cwd.rglob(f"*{LOG_EXT}"))
    if not log_files:
        print(f"No {LOG_EXT} files found.")
        return
    print(f"Found {len(log_files)} log file(s). Cleaning...\n")
    for log_file in log_files:
        clean_file(log_file)
    print(f"\nDone. Processed {len(log_files)} file(s).")


if __name__ == "__main__":
    main()
