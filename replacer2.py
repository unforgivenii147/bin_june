#!/usr/bin/env python3
"""
Text replacer for Python files in current directory.
Replaces exact text matches in all .py files.
"""

import sys
from pathlib import Path


def replace_in_file(filepath: Path, old_text: str, new_text: str) -> bool:
    """Replace text in a single file."""
    try:
        # Read file content
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if old_text exists
        if old_text not in content:
            return False

        # Replace text
        new_content = content.replace(old_text, new_text)

        # Write back to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python replacer.py <old_text> <new_text>")
        print("\nExample:")
        print('python replacer.py "    try:\\n    path=Path(path)" "    path=Path(path)\\n    try:"')
        sys.exit(1)

    old_text = sys.argv[1]
    new_text = sys.argv[2]

    # Convert escaped sequences
    old_text = old_text.encode().decode("unicode_escape")
    new_text = new_text.encode().decode("unicode_escape")

    # Find all Python files in current directory
    cwd = Path(".")
    py_files = list(cwd.glob("*.py"))

    if not py_files:
        print("No Python files found in current directory.")
        sys.exit(0)

    print(f"Found {len(py_files)} Python file(s)")
    print(f"Replacing: {repr(old_text)}")
    print(f"With:      {repr(new_text)}")
    print("-" * 50)

    modified_count = 0

    for py_file in py_files:
        if replace_in_file(py_file, old_text, new_text):
            print(f"✓ Modified: {py_file}")
            modified_count += 1
        else:
            print(f"  Skipped: {py_file} (no match)")

    print("-" * 50)
    print(f"Done! Modified {modified_count} file(s).")


if __name__ == "__main__":
    main()
_
