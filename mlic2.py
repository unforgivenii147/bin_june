#!/data/data/com.termux/files/usr/bin/python

"""
Detect and optionally remove repeated comment lines (starting with '#')
in Python files under the current directory.
Repeated means the exact same comment line appears in at least two places
(across files or within the same file). This is intended to catch license
headers and similar boilerplate that developers paste into many files.
Excluded lines:
  - Shebang lines (e.g.,
  - Lines starting with '# type', '# fmt', '# pylint', '# ruff', '# mypy'
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

EXCLUDED_PREFIXES = ["#!", "# type", "# fmt", "# pylint", "# ruff", "# mypy"]


def is_comment_line(stripped: str) -> bool:
    """Return True if the stripped line is a comment that should be checked for repetition."""
    if not stripped.startswith("#"):
        return False
    return not any((stripped.startswith(prefix) for prefix in EXCLUDED_PREFIXES))


def collect_comments(root: Path) -> Dict[str, List[Tuple[Path, int, str]]]:
    """
    Walk *root* recursively and collect all comment lines from .py files.
    Returns a dict mapping stripped comment text -> list of (file, line_number, original_line).
    """
    comments: Dict[str, List[Tuple[Path, int, str]]] = defaultdict(list)
    for py_file in root.rglob("*.py"):
        try:
            with open(py_file, encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError) as e:
            print(f"Warning: cannot read {py_file}: {e}", file=sys.stderr)
            continue
        for lineno, raw_line in enumerate(lines, start=1):
            original = raw_line.rstrip("\n\r")
            stripped = original.strip()
            if is_comment_line(stripped):
                comments[stripped].append((py_file, lineno, original))
    return comments


def find_repeated(
    comments: Dict[str, List[Tuple[Path, int, str]]],
) -> Dict[str, List[Tuple[Path, int, str]]]:
    """Return only those comment lines that appear more than once."""
    return {line: occurrences for line, occurrences in comments.items() if len(occurrences) >= 2}


def report(repeated: Dict[str, List[Tuple[Path, int, str]]]) -> None:
    """Print the repeated comment lines and their locations."""
    if not repeated:
        print("No repeated comment lines found.")
        return
    print("Found repeated comment lines:")
    for line, occurrences in repeated.items():
        print(f"\n  {line!r}")
        for filepath, lineno, _ in occurrences:
            print(f"    {filepath}:{lineno}")


def remove_repeated(repeated: Dict[str, List[Tuple[Path, int, str]]]) -> None:
    """Remove all occurrences of the given repeated comment lines from their files."""
    lines_to_remove = set(repeated.keys())
    files_to_process = {filepath for occurrences in repeated.values() for filepath, _, _ in occurrences}
    removed_total = 0
    files_changed = 0
    for filepath in files_to_process:
        try:
            with open(filepath, encoding="utf-8") as f:
                original_lines = f.readlines()
        except OSError as e:
            print(f"Warning: cannot read {filepath} for removal: {e}", file=sys.stderr)
            continue
        new_lines = []
        file_removed = 0
        for raw_line in original_lines:
            original = raw_line.rstrip("\n\r")
            stripped = original.strip()
            if stripped in lines_to_remove:
                file_removed += 1
                continue
            new_lines.append(raw_line)
        if file_removed == 0:
            continue
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except OSError as e:
            print(f"Error: cannot write {filepath}: {e}", file=sys.stderr)
            continue
        removed_total += file_removed
        files_changed += 1
        print(f"Removed {file_removed} line(s) from {filepath}")
    print(f"\nDone. Removed {removed_total} repeated comment line(s) from {files_changed} file(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-r",
        "--remove",
        action="store_true",
        help="Remove found repeated comment lines from files",
    )
    args = parser.parse_args()
    root = Path.cwd()
    comments = collect_comments(root)
    repeated = find_repeated(comments)
    if args.remove:
        if not repeated:
            print("No repeated comment lines to remove.")
        else:
            remove_repeated(repeated)
    else:
        report(repeated)


if __name__ == "__main__":
    main()
