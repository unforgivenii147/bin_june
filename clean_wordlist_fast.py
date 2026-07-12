#!/data/data/com.termux/files/usr/bin/env python
import os
import re
import sys
import tempfile
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


THRESHOLD = 5 * 1024 * 1024
RE_REPEAT = re.compile(r"^(.)\1+$", re.IGNORECASE)


def should_skip(line: str) -> bool:
    s = line.rstrip("\n")
    return bool(RE_REPEAT.fullmatch(s))


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <wordlist.txt>", file=sys.stderr)
        sys.exit(1)
    fname = sys.argv[1]
    fpath = Path(fname)
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="wordlist_", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with (
            os.fdopen(tmp_fd, "w", encoding="utf-8", errors="ignore") as out,
            fpath.open("r", encoding="utf-8", errors="ignore") as inp,
        ):
            for line in inp:
                if not should_skip(line):
                    out.write(line)
        tmp_path.replace(fpath)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


if __name__ == "__main__":
    main()
