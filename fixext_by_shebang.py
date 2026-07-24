#!/data/data/com.termux/files/home/.local/bin/python
"""
Fix file extensions based on shebang detection.
Scans files in current directory and renames them with .py or .sh extensions
if they contain appropriate shebangs but have wrong or missing extensions.
"""

from __future__ import annotations

import os
import sys

# Shebang to extension mapping
SHEBANG_MAP = {
    "python": ".py",
    "python3": ".py",
    "python2": ".py",
    "bash": ".sh",
    "sh": ".sh",
    "zsh": ".sh",
    "ksh": ".sh",
    "dash": ".sh",
}

# Target extensions we care about
TARGET_EXTENSIONS = {".py", ".sh"}


def detect_shebang(filepath):
    """Read the first line of a file and detect if it contains a shebang."""
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            first_line = f.readline().strip()
            if first_line.startswith("#!"):
                # Extract the interpreter from shebang
                interpreter = first_line[2:].strip()
                # Handle /usr/bin/env python3 style shebangs
                if "/env " in interpreter:
                    interpreter = interpreter.split("/env ")[-1]
                # Handle /usr/bin/python3 style shebangs
                else:
                    interpreter = os.path.basename(interpreter)

                # Check against our mapping
                for key, ext in SHEBANG_MAP.items():
                    if key in interpreter.lower():
                        return ext
    except OSError as e:
        print(f"Error reading {filepath}: {e}")
    return None


def should_rename(filepath, target_ext):
    """Check if file needs renaming based on target extension."""
    current_ext = os.path.splitext(filepath)[1].lower()

    # Case 1: Current extension matches target - no change needed
    if current_ext == target_ext:
        return False

    # Case 2: No extension or wrong extension - needs rename
    return True


def rename_file(filepath, target_ext):
    """Rename file to have the target extension."""
    directory = os.path.dirname(filepath)
    basename = os.path.splitext(os.path.basename(filepath))[0]

    # If file has no extension, keep the original name
    if not os.path.splitext(filepath)[1]:
        basename = os.path.basename(filepath)

    new_name = f"{basename}{target_ext}"
    new_path = os.path.join(directory, new_name)

    # Handle name conflicts
    counter = 1
    while os.path.exists(new_path) and new_path != filepath:
        new_name = f"{basename}_{counter}{target_ext}"
        new_path = os.path.join(directory, new_name)
        counter += 1

    try:
        # Only rename if the new path is different
        if new_path != filepath:
            os.rename(filepath, new_path)
            return new_path
    except OSError as e:
        print(f"Error renaming {filepath} to {new_path}: {e}")
        return None

    return None


def main():
    """Main function to process all files in current directory."""
    # Dry run mode
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    if dry_run:
        print("*** DRY RUN MODE - No files will be renamed ***\n")

    current_dir = os.getcwd()
    renamed_count = 0
    skipped_count = 0

    # Scan all files in current directory (non-recursive)
    for item in os.listdir(current_dir):
        filepath = os.path.join(current_dir, item)

        # Skip directories and special files
        if not os.path.isfile(filepath):
            continue

        # Skip files that are not executable (optional, can be removed)
        # if not os.access(filepath, os.X_OK):
        #     continue

        # Detect shebang
        target_ext = detect_shebang(filepath)

        if target_ext is None:
            if verbose:
                print(f"  SKIP: {item} (no recognized shebang)")
            continue

        # Check if file needs renaming
        if not should_rename(filepath, target_ext):
            if verbose:
                print(f"  SKIP: {item} (already has correct extension)")
            skipped_count += 1
            continue

        # Perform rename
        if dry_run:
            new_name = os.path.splitext(item)[0] + target_ext
            print(f"  WOULD RENAME: {item} -> {new_name}")
            renamed_count += 1
        else:
            result = rename_file(filepath, target_ext)
            if result:
                print(f"  RENAMED: {item} -> {os.path.basename(result)}")
                renamed_count += 1
            else:
                skipped_count += 1

    # Summary
    print("\nSummary:")
    if dry_run:
        print(f"  Would rename: {renamed_count} files")
    else:
        print(f"  Renamed: {renamed_count} files")
    print(f"  Skipped: {skipped_count} files")


if __name__ == "__main__":
    main()
