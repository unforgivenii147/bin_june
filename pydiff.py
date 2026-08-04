#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from pathlib import Path
from dh import cprint

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def read_lines(path: str | Path, ke: bool = True) -> list[str]:
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
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


def process_files(path1: Path, path2: Path) -> None:
    lines1 = read_lines(path1)
    lines2 = read_lines(path2)
    only_in_first = [p for p in lines1 if p not in lines2]
    only_in_second = [p for p in lines2 if p not in lines1]
    common_lines = [p for p in lines1 if p in lines2]
    if only_in_first:
        cprint(f"only in {path1.name} :", "cyan")
        for line in only_in_first:
            cprint(f"  - {line}", "green")
    if only_in_second:
        cprint(f"only in {path2.name} :", "cyan")
        for line in only_in_second:
            cprint(f"  - {line}", "yellow")
    cprint(
        f"""common lines: {len(common_lines)}
only in {path1.name}: {len(only_in_first)}
only in {path2.name}: {len(only_in_second)}""",
        "blue",
    )


if __name__ == "__main__":
    f1 = Path(sys.argv[1])
    f2 = Path(sys.argv[2])
    process_files(f1, f2)
