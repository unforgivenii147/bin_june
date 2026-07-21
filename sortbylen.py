#!/data/data/com.termux/files/usr/bin/env python

"""Module for sortbylen.py."""

from __future__ import annotations

import sys
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
THRESHOLD = 1024 * 1024


def read_lines(path: str | Path, ke: bool = True) -> list[str]:
    path = Path(path)
    if path.stat().st_size > THRESHOLD:
        return read_lines_mmap(path, ke)
    data = Path(path).read_bytes()
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=ke)
    if not lines[-1].endswith(("\n", "\r\n", "\r")) and data.endswith(b"\n"):
        lines.append("")
    return lines


def read_lines_mmap(path: Path, keep_ends: bool = True) -> list[str]:
    import mmap

    size = Path(path).stat().st_size
    with Path(path).open("rb") as f, mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ) as mm:
        text = mm[:].decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=keep_ends)
    if not lines[-1].endswith(("\n", "\r\n", "\r")) and size > 0 and text.endswith("\n"):
        lines.append("")
    return lines


def sort_by_length(lines: list[str]) -> list[str]:
    return sorted(lines, key=len)


if __name__ == "__main__":
    path = Path(sys.argv[1].strip())
    lines = read_lines(path, ke=True)
    sorted_lines = sort_by_length(lines)
    path.write_text("".join(sorted_lines), encoding="utf8")
    print(f"{path.name} updated")
