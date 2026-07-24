#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

COMMENT_PREFIXES = "#", "//", "--"


def is_comment(line: str) -> bool:
    stripped = line.lstrip()
    return any(stripped.startswith(prefix) for prefix in COMMENT_PREFIXES)


def process_lines(lines: list[str], start_idx, end_idx, unique=False, comments=True):
    target_slice = lines[start_idx:end_idx]
    if comments:
        working = target_slice[:]
        removed_lines = []
        if unique:
            seen = set()
            unique_lines = []
            for line in working:
                if line not in seen:
                    seen.add(line)
                    unique_lines.append(line)
                else:
                    removed_lines.append(line.rstrip("\n"))
            working = unique_lines
        working.sort()
        return working, removed_lines
    sortable_lines = []
    comment_positions = {}
    for i, line in enumerate(target_slice):
        if is_comment(line):
            comment_positions[i] = line
        else:
            sortable_lines.append(line)
    removed_lines = []
    if unique:
        seen = set()
        unique_lines = []
        for line in sortable_lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
            else:
                removed_lines.append(line.rstrip("\n"))
        sortable_lines = unique_lines
    sortable_lines.sort()
    rebuilt = []
    sort_idx = 0
    for i in range(len(target_slice)):
        if i in comment_positions:
            rebuilt.append(comment_positions[i])
        else:
            rebuilt.append(sortable_lines[sort_idx])
            sort_idx += 1
    return rebuilt, removed_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Sort lines in a file within a given line range.")
    parser.add_argument("filename", help="Path to file")
    parser.add_argument("start_line", type=int, help="Start line (1-based)")
    parser.add_argument("end_line", type=int, help="End line (1-based, inclusive)")
    parser.add_argument(
        "-c",
        "--comments",
        action="store_true",
        default=True,
        help="Include comment lines in sorting",
    )
    parser.add_argument(
        "-u",
        "--unique",
        action="store_true",
        default=False,
        help="Remove duplicate lines within range",
    )
    args = parser.parse_args()
    file_path = Path(args.filename)
    if not file_path.exists():
        print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if args.start_line < 1 or args.end_line < args.start_line:
        print("Error: invalid line range.", file=sys.stderr)
        sys.exit(1)
    try:
        with file_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        total_lines = len(lines)
        if args.end_line > total_lines:
            print(
                f"Error: end line {args.end_line} exceeds file length {total_lines}.",
                file=sys.stderr,
            )
            sys.exit(1)
        start_idx = args.start_line - 1
        end_idx = args.end_line
        rebuilt_slice, removed_lines = process_lines(
            lines, start_idx, end_idx, unique=args.unique, comments=args.comments
        )
        new_lines = lines[:start_idx] + rebuilt_slice + lines[end_idx:]
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as tmp_file:
            tmp_file.writelines(new_lines)
            temp_name = tmp_file.name
        shutil.move(temp_name, file_path)
        if args.unique and removed_lines:
            print("Removed duplicate lines:")
            for line in removed_lines:
                print(f"  {line}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
