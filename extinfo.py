#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import sys
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = "B", "KB", "MB", "GB", "TB"
    if sz == 0:
        return "0 B"
    i = min((int(sz).bit_length() - 1) // 10, len(units) - 1)
    value = sz / 1024**i
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: script.py <extension>")
        print("Example: script.py py")
        sys.exit(1)
    ext = sys.argv[1].lstrip(".")
    cwd = Path.cwd()
    files = list(cwd.rglob(f"*.{ext}"))
    if not files:
        print(f"No .{ext} files found in current directory")
        sys.exit(0)
    total_size = sum(f.stat().st_size for f in files)
    count = len(files)
    print(f"Total number of .{ext} files: {count}")
    print(f"Total size of .{ext} files: {fsz(total_size)}")


if __name__ == "__main__":
    main()
