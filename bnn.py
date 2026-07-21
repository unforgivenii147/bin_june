#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def process_file(fname) -> None:
    path = Path(path)
    content = fname.read_text(encoding="utf-8")
    content = content.replace("\\n", "\n")
    fname.write_text(content, encoding="utf-8")
    print(f"{fname.name} updated.")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from dh import get_pyfiles, mpf3

    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_pyfiles(cwd)
    mpf3(process_file, files)
