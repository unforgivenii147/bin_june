#!/data/data/com.termux/files/usr/bin/env python

"""Module for wf.py."""

from __future__ import annotations

import os
import sys
import time

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def tail_file(fname: str, n=10):
    try:
        with open(fname) as f:
            lines = f.readlines()
            return lines[-n:] if lines else []
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return []


def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <filename>", file=sys.stderr)
        sys.exit(1)
    fname = sys.argv[1]
    if not os.path.isfile(fname):
        print(f"Error: File '{fname}' not found", file=sys.stderr)
        sys.exit(1)
    last_mtime = os.stat(fname).st_mtime
    print(f"Watching '{fname}'... (Press Ctrl+C to exit)\n")
    try:
        while True:
            current_mtime = os.stat(fname).st_mtime
            if current_mtime > last_mtime:
                last_mtime = current_mtime
                print(f"\n--- Change detected at {time.strftime('%H:%M:%S')} ---")
                lines = tail_file(fname, n=10)
                for line in lines:
                    print(line.rstrip("\n"))
                tail_text = "".join(lines)
                if "boostraped 100%" in tail_text:
                    print("\n✓ Bootstrap complete detected! Exiting...\n")
                    sys.exit(0)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nWatcher stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
