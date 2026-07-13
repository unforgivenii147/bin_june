#!/data/data/com.termux/files/usr/bin/env python

from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines(keepends=False)
    if not lines:
        return False
    nl = []
    i = 0
    for line in lines:
        if line.startswith("#!"):
            i += 1
    if i > 1:
        return True
    return False


def main() -> None:
    fixed = 0
    cwd = Path.cwd()
    for file in cwd.rglob("*.py"):
        if fix_file(file):
            fixed += 1
            print(f"{file} has 2 shebang")
    print(f"\nDone. Updated {fixed} files.")


if __name__ == "__main__":
    main()
