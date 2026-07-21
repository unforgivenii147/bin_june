#!/data/data/com.termux/files/usr/bin/env python
"""
Search the current directory for Windows and macOS related files on a Linux system.
Optionally remove them with the -a (--auto-remove) CLI argument.
"""

from __future__ import annotations

import argparse
import os

# File extensions / names to search for
WINDOWS_FILES = {".exe", ".dll", ".bat", ".com", ".msi", ".vbs", ".ps1"}
MACOS_FILES = {".dmg", ".app", ".DS_Store", ".plist", ".pkg"}


def find_target_files(root_dir):
    target_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            # Check by extension or exact name
            if any(filename.lower().endswith(ext) for ext in WINDOWS_FILES):
                target_files.append(os.path.join(dirpath, filename))
            elif any(filename.lower().endswith(ext) for ext in MACOS_FILES):
                target_files.append(os.path.join(dirpath, filename))
            elif filename == ".DS_Store":
                target_files.append(os.path.join(dirpath, filename))
    return target_files


def main():
    parser = argparse.ArgumentParser(
        description="Search for Windows/macOS files in the current directory and optionally remove them."
    )
    parser.add_argument(
        "-a", "--auto-remove", action="store_true", help="Automatically remove found files after confirmation."
    )
    args = parser.parse_args()

    current_dir = os.getcwd()
    print(f"Scanning directory: {current_dir}\n")

    found_files = find_target_files(current_dir)

    if not found_files:
        print("No Windows or macOS related files found.")
        return
    cwd = Path.cwd().resolve()
    print(f"Found {len(found_files)} file(s):\n")
    for file_path in found_files:
        print(f"  {file_path.relative_to(cwd)}")

    if args.auto_remove:
        print("\n" + "=" * 35)
        deleted_count = 0
        for file_path in found_files:
            try:
                os.remove(file_path)
                print(f"Deleted: {file_path}")
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        print(f"\nDeleted {deleted_count} of {len(found_files)} files.")


if __name__ == "__main__":
    main()
