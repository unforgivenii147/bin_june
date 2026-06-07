#!/data/data/com.termux/files/usr/bin/python

import argparse
import re
import sys
from pathlib import Path

from dh import get_nobinary

TAB_PATTERN = re.compile("\\t")
SPACE_REPLACEMENT = " " * 4
cwd = Path.cwd()


def replace_tabs_in_file(file_path: Path):
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"Error: Could not decode {file_path.name} with UTF-8. Skipping.", file=sys.stderr)
        return
    except OSError as e:
        print(f"Error reading {file_path.name}: {e}. Skipping.", file=sys.stderr)
        return
    if not TAB_PATTERN.search(content):
        return
    new_content = TAB_PATTERN.sub(SPACE_REPLACEMENT, content)
    try:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"{file_path.relative_to(cwd)} updated")
    except OSError as e:
        print(f"Error writing to {file_path.name}: {e}. Skipping.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Replaces tab characters with 4 spaces in Python files or specified text files."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific files to process. If none, all *.py files in current directory and subdirectories are processed.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output (e.g., skip messages for files without tabs)."
    )
    args = parser.parse_args()
    if args.files:
        file_paths = [Path(f) for f in args.files]
        for f_path in file_paths:
            if not f_path.exists():
                print(f"Warning: File '{f_path}' not found. Skipping.", file=sys.stderr)
        file_paths = [f for f in file_paths if f.exists()]
    else:
        file_paths = get_nobinary(cwd)
    file_paths.sort()
    if not file_paths:
        print("No Python files found to process.")
        sys.exit(0)
    print(f"Found {len(file_paths)} files to process.")
    for file_path in file_paths:
        replace_tabs_in_file(file_path)


if __name__ == "__main__":
    main()
