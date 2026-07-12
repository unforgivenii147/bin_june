#!/data/data/com.termux/files/usr/bin/env python
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def main() -> None:
    count = 0
    root = Path.cwd()

    # Get all directories recursively, sorted by depth (deepest first)
    dirs = [p for p in root.rglob("*") if p.is_dir()]
    dirs.sort(key=lambda p: len(p.parts), reverse=True)

    for dir_path in dirs:
        try:
            dir_path.rmdir()  # Only removes if empty
            print(f"removing empty dir: {dir_path}")
            count += 1
        except OSError:
            # Directory not empty - skip
            pass

    print(f"total {count} empty dirs removed")


if __name__ == "__main__":
    main()
