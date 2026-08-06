#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import sys
from collections.abc import Callable
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
from dh import mpf3, runcmd


def process_pkg(pkg) -> None:
    print(f"creating stubs for {pkg}")
    cmd = ["pyright", "--createstub", str(pkg)]
    _, _, _ = runcmd(cmd, show_output=True)


def main() -> None:
    std_pkgs = list(STDLIB)
    mpf3(process_pkg, std_pkgs)


if __name__ == "__main__":
    sys.exit(main())
