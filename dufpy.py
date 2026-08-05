#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import ast
from collections.abc import Callable
from os import scandir as os_scandir
from pathlib import Path

from dh import cprint, get_pyfiles, is_binary, is_python_file
from dh.jobutils import mpf3
from xxhash import xxh64_hexdigest

CHUNK_SIZE = 1024 * 1024

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def process_file(path) -> tuple[str, Path]:
    path = Path(path)
    return xxh64_hexdigest(ast.unparse(ast.parse(path.read_text(encoding="utf-8")))), path


def main() -> None:
    cwd = Path.cwd()
    files = get_pyfiles(cwd)
    fd = {}
    results = mpf3(process_file, files)
    for result in results:
        hash, path = result
        fd.setdefault(hash, []).append(path)
    for h, p in fd.items():
        if len(p) > 1:
            print(f"files with hash: {h}")
            for path in p:
                print(f"  - {path}")
                path.unlink()
    deleted = 0
    for h, p in fd.items():
        if len(p) > 1:
            for path in p[1:]:
                deleted += 1
                if path.exists():
                    path.unlink()
    if deleted:
        cprint(f"{deleted} files removed.", "cyan")


if __name__ == "__main__":
    main()
