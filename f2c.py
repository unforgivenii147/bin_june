#!/data/data/com.termux/files/usr/bin/env python


import sys

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


if __name__ == "__main__":
    farenheit = int(sys.argv[1])
    celecius = (farenheit - 32) * 5 / 9
    print(f"{celecius:.2f}")
