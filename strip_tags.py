#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_removed_lines(txt1, txt2):
    return list({l for l in txt1.splitlines() if l} - {l for l in txt2.splitlines() if l})


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


INPLACE = "-w" in sys.argv
if __name__ == "__main__":
    fn = Path(sys.argv[1])
    content = fn.read_text(encoding="utf-8")
    lines = read_lines(fn, ke=False)
    nl = []
    for line in lines:
        if "<:" in line or ">:" in line:
            continue
        text = re.sub(r"<[^>]*>", "", line)
        nl.append(text)
    new_content = "\n".join(nl)
    removed, _added = get_removed_lines(content, new_content)
    for k in removed:
        print(f" - {k}")
    if INPLACE:
        fn.write_text(new_content, encoding="utf8")
    print("file didnt updated.\n for update inplace rerun with -w arg")
