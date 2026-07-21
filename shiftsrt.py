#!/data/data/com.termux/files/usr/bin/env python

"""Module for shiftsrt.py."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

TIMESTAMP_RE = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s-->\s(\d{2}:\d{2}:\d{2},\d{3})")
ONE_SEC_MS = 1000


def to_ms(ts: str) -> int:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def from_ms(ms: int) -> str:
    ms = max(ms, 0)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def shift_content(text: str, shift_ms: int) -> str:

    def repl(m) -> str:
        a, b = m.groups()
        return f"{from_ms(to_ms(a) + shift_ms)} --> {from_ms(to_ms(b) + shift_ms)}"

    return TIMESTAMP_RE.sub(repl, text)


def process_file(path: Path, shift_ms: int) -> None:
    path = Path(path)
    path.write_text(shift_content(path.read_text(encoding="utf-8"), shift_ms), encoding="utf-8")
    print(f"✔ {path}")


def main() -> None:
    raw = sys.argv[1:]
    force_shift = None
    if raw and raw[0] in {"+", "-"}:
        force_shift = ONE_SEC_MS if raw[0] == "+" else -ONE_SEC_MS
        raw = raw[1:]
    ap = argparse.ArgumentParser(description="Shift SRT subtitles inplace (batch supported)")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("-r", "--recursive", action="store_true")
    ap.add_argument("-s", "--shift", type=float, default=0.0)
    ap.add_argument("--plus", action="store_true", help="Shift +1s")
    ap.add_argument("--minus", action="store_true", help="Shift -1s")
    args = ap.parse_args(raw)
    if force_shift is not None:
        shift_ms = force_shift
    elif args.plus:
        shift_ms = ONE_SEC_MS
    elif args.minus:
        shift_ms = -ONE_SEC_MS
    else:
        shift_ms = int(args.shift * 1000)
    path = Path(args.path)
    if path.is_file():
        process_file(path, shift_ms)
        return
    glob = "**/*.srt" if args.recursive else "*.srt"
    for f in sorted(path.glob(glob)):
        process_file(f, shift_ms)


if __name__ == "__main__":
    main()
