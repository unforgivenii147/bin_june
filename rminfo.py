#!/data/data/com.termux/files/home/.local/bin/python
"""
Script to remove author/email/time info block from Python files recursively.
Handles both .py files and Python files without extension (detected via shebang).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Pattern to match your info block
INFO_BLOCK_PATTERN = re.compile(
    r"^# Author\s*:\s*isaac\s*\n"
    r"# Email\s*:\s*mkalafsaz@gmail\.com\s*\n"
    r"# Time\s*:\s*.*?\n",
    re.MULTILINE,
)

# Python shebang patterns
PYTHON_SHEBANG_PATTERNS = [
    re.compile(r"^#!.*python", re.IGNORECASE),
    re.compile(r"^#!.*python3", re.IGNORECASE),
]


def is_python_file(file_path):
    """Check if a file is a Python file (by extension or shebang)."""
    # Check extension
    if file_path.suffix == ".py":
        return True

    # Check for shebang in files without extension
    if not file_path.suffix:
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                first_line = f.readline()
                for pattern in PYTHON_SHEBANG_PATTERNS:
                    if pattern.match(first_line):
                        return True
        except Exception:
            pass

    return False


def remove_info_block(file_path):
    """Remove the info block from a Python file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Skip if file doesn't contain the info block
        if "Author : isaac" not in content:
            return False

        # Remove the info block
        new_content = INFO_BLOCK_PATTERN.sub("", content)

        # Write back only if changed
        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Main function to process all Python files recursively."""
    start_dir = Path(".")
    removed_count = 0
    files_checked = 0

    # Find all files recursively
    for file_path in start_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip common non-Python files without extension
        name = file_path.name
        if name in [".DS_Store", ".gitignore", "README", "LICENSE", "Makefile"]:
            continue

        # Check if it's a Python file
        if not is_python_file(file_path):
            continue

        files_checked += 1

        # Try to remove info block
        if remove_info_block(file_path):
            print(f"✓ Removed info block from: {file_path}")
            removed_count += 1

    print("\nSummary:")
    print(f"  Python files checked: {files_checked}")
    print(f"  Info blocks removed: {removed_count}")


if __name__ == "__main__":
    main()
