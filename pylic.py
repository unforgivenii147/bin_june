#!/data/data/com.termux/files/usr/bin/env python

"""
Detect and optionally remove repeated multi-line comment blocks (starting with '#')
in Python files under the current directory.
Repeated means the exact same consecutive group of comment lines (2 or more lines)
appears in at least two places (across files or within the same file).
This is intended to catch license headers and similar boilerplate that developers
paste into many files.
Excluded lines:
  - Shebang lines (e.g.,
  - Lines starting with '# type', '# fmt', '# pylint', '# ruff', '# mypy'
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

EXCLUDED_PREFIXES = ["#!", "# type", "# fmt", "# pylint", "# ruff", "# mypy"]


def is_comment_line(stripped: str) -> bool:
    if not stripped.startswith("#"):
        return False
    return not any(stripped.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def extract_comment_blocks(lines: List[str], start_line: int) -> List[Tuple[str, int, List[str]]]:
    blocks = []
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        original = raw_line.rstrip("\n\r")
        stripped = original.strip()
        if is_comment_line(stripped):
            block_start = i
            block_lines = []
            block_stripped = []
            while i < len(lines):
                raw_line = lines[i]
                original = raw_line.rstrip("\n\r")
                stripped = original.strip()
                if is_comment_line(stripped):
                    block_lines.append(original)
                    block_stripped.append(stripped)
                    i += 1
                else:
                    break
            if len(block_stripped) >= 2:
                block_text = "\n".join(block_stripped)
                blocks.append((block_text, start_line + block_start, block_lines))
            else:
                i += 1
        else:
            i += 1
    return blocks


def collect_comment_blocks(root: Path) -> Dict[str, List[Tuple[Path, int, List[str]]]]:
    blocks: Dict[str, List[Tuple[Path, int, List[str]]]] = defaultdict(list)
    for py_file in root.rglob("*.py"):
        try:
            with open(py_file, encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError) as e:
            print(f"Warning: cannot read {py_file}: {e}", file=sys.stderr)
            continue
        file_blocks = extract_comment_blocks(lines, 1)
        for block_text, start_lineno, original_lines in file_blocks:
            blocks[block_text].append((py_file, start_lineno, original_lines))
    return blocks


def find_repeated_blocks(
    blocks: Dict[str, List[Tuple[Path, int, List[str]]]],
) -> Dict[str, List[Tuple[Path, int, List[str]]]]:
    return {block: occurrences for block, occurrences in blocks.items() if len(occurrences) >= 2}


def report(repeated: Dict[str, List[Tuple[Path, int, List[str]]]]) -> None:
    if not repeated:
        print("No repeated multi-line comment blocks found.")
        return
    print(f"Found {len(repeated)} repeated multi-line comment block(s):")
    for i, (block_text, occurrences) in enumerate(repeated.items(), 1):
        print(f"""
--- Block {i} ({len(occurrences)} occurrences, {block_text.count(chr(10)) + 1} lines) ---""")
        for line in block_text.split("\n"):
            print(f"  {line}")
        print(f"  Found in:")
        for filepath, lineno, _ in occurrences:
            print(f"    {Path(filepath).name}:{lineno}")


def remove_repeated_blocks(repeated: Dict[str, List[Tuple[Path, int, List[str]]]]) -> None:
    file_removals: Dict[Path, List[Tuple[int, List[str]]]] = defaultdict(list)
    for block_text, occurrences in repeated.items():
        for filepath, start_lineno, original_lines in occurrences:
            file_removals[filepath].append((start_lineno, original_lines))
    removed_total = 0
    files_changed = 0
    for filepath, removals in file_removals.items():
        try:
            with open(filepath, encoding="utf-8") as f:
                original_lines = f.readlines()
        except OSError as e:
            print(f"Warning: cannot read {filepath} for removal: {e}", file=sys.stderr)
            continue
        lines_to_remove = set()
        for start_lineno, block_lines in removals:
            for offset in range(len(block_lines)):
                lines_to_remove.add(start_lineno + offset)
        new_lines = []
        file_removed = 0
        for lineno, raw_line in enumerate(original_lines, start=1):
            if lineno in lines_to_remove:
                file_removed += 1
                continue
            new_lines.append(raw_line)
        if file_removed == 0:
            continue
        try:
            new_content = "".join(new_lines)
            _ = ast.parse(new_content)
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            removed_total += file_removed
            files_changed += 1
            print(f"Removed {file_removed} line(s) from {filepath.name}")
        except SyntaxError as e:
            print(
                f"Warning: Removing blocks from {filepath} would create invalid Python, skipping: {e}",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"Error: cannot write {filepath}: {e}", file=sys.stderr)
    print(f"\nDone. Removed {removed_total} repeated comment line(s) from {files_changed} file(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-r",
        "--remove",
        action="store_true",
        help="Remove found repeated multi-line comment blocks from files",
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=2,
        help="Minimum number of consecutive comment lines to consider a block (default: 2)",
    )
    args = parser.parse_args()
    root = Path.cwd()
    blocks = collect_comment_blocks(root)
    repeated = find_repeated_blocks(blocks)
    if args.remove:
        if not repeated:
            print("No repeated multi-line comment blocks to remove.")
        else:
            remove_repeated_blocks(repeated)
    else:
        report(repeated)


if __name__ == "__main__":
    main()
