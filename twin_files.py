#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import argparse
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def remove_ipynb_if_md_exists(root: Path, dry_run: bool = True) -> None:
    removed = 0
    checked = 0
    for ipynb_path in root.rglob("*.ipynb"):
        checked += 1
        md_path = ipynb_path.with_suffix(".md")
        if md_path.exists():
            print(f"[MATCH] {ipynb_path}  ->  {md_path}")
            if not dry_run:
                try:
                    ipynb_path.unlink()
                    print(f"[REMOVED] {ipynb_path}")
                    removed += 1
                except Exception as e:
                    print(f"[ERROR] Could not remove {ipynb_path}: {e}")
            else:
                print(f"[DRY RUN] Would remove {ipynb_path}")
    print("\n--- Summary ---")
    print(f"Checked: {checked}")
    print(f"Removed: {removed}" if not dry_run else "Dry run only. No files removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove .ipynb files if a .md file with the same name exists.")
    parser.add_argument("--apply", action="store_true", help="Actually delete files (default is dry run).")
    args = parser.parse_args()
    cwd = Path.cwd()
    remove_ipynb_if_md_exists(cwd, dry_run=not args.apply)
