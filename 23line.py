#!/data/data/com.termux/files/usr/bin/env python

"""Module for 23line.py."""


from __future__ import annotations

from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
EXT = {".py", ".h", ".c", ".cpp", ".cc", ".cxx", ".hh", ".hpp", ".hxx"}


def get_first_13(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
        return "".join(lines[:23])
    except OSError:
        return ""


def main() -> None:
    output_path = Path("all.txt").resolve()
    collected = []
    for file_path in Path.cwd().rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix not in EXT:
            continue
        if file_path.resolve() == output_path:
            continue
        snippet = get_first_13(file_path)
        if snippet:
            collected.append(snippet)
    unique_collected = list(set(collected))
    output_path.write_text("\n\n\n".join(unique_collected), encoding="utf-8")
    print(f"Unique snippets saved → {output_path}")
    print(f"Total unique blocks: {len(unique_collected)}")


if __name__ == "__main__":
    main()
