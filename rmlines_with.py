#!/data/data/com.termux/files/usr/bin/env python

import sys
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def clean_file(path: Path, target: str) -> None:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    cleaned = [p for p in lines if not target in p]
    result = "".join(cleaned)
    path.write_text(result, encoding="utf-8")


def main() -> None:
    fn = Path(sys.argv[1])
    str_to_find = sys.argv[2]
    clean_file(fn, str_to_find)


if __name__ == "__main__":
    main()
