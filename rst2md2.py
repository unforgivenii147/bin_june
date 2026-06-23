#!/data/data/com.termux/files/usr/bin/python

"""
Convert .rst files to .md in-place using pandoc.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def convert_file(filepath: Path, backup=True, remove_original=False) -> bool:
    """Convert .rst to .md using pandoc."""
    filepath = Path(filepath)

    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return False

    if filepath.suffix.lower() != ".rst":
        print(f"Skipping {filepath}: not an .rst file")
        return False

    md_path = filepath.with_suffix(".md")

    # Create backup if requested
    if backup and not remove_original:
        backup_path = filepath.with_suffix(".rst.bak")
        import shutil

        shutil.copy2(filepath, backup_path)
        print(f"Backup created: {backup_path}")

    # Convert using pandoc
    try:
        result = subprocess.run(
            ["pandoc", "-f", "rst", "-t", "gfm", "-o", str(md_path), str(filepath)],
            capture_output=True,
            text=True,
            check=True,
        )

        if remove_original:
            filepath.unlink()
            print(f"Converted and removed original: {filepath} -> {md_path}")
        else:
            print(f"Converted: {filepath} -> {md_path}")

        return True

    except subprocess.CalledProcessError as e:
        print(f"Error converting {filepath}: {e.stderr}")
        return False


def convert_recursive(directory: Path, backup: bool = True, remove_original: bool = False) -> None:
    """Convert all .rst files recursively."""
    directory = Path(directory)
    if not directory.exists():
        print(f"Error: {directory} not found")
        return

    rst_files = list(directory.rglob("*.rst"))
    if not rst_files:
        print(f"No .rst files found in {directory}")
        return

    print(f"Found {len(rst_files)} .rst files")
    success_count = 0

    for rst_file in rst_files:
        if convert_file(rst_file, backup, remove_original):
            success_count += 1

    print(f"\nConverted {success_count}/{len(rst_files)} files")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert .rst files to .md using pandoc")
    parser.add_argument("paths", nargs="+", help="Files or directories to convert")
    parser.add_argument("-r", "--recursive", action="store_true", help="Process directories recursively")
    parser.add_argument("--no-backup", action="store_true", help="Do not create backup files")
    parser.add_argument("--remove-original", action="store_true", help="Remove original .rst files")

    args = parser.parse_args()

    # Check if pandoc is installed
    try:
        subprocess.run(["pandoc", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: pandoc is not installed. Install it with:")
        print("  - Termux: pkg install pandoc")
        print("  - Ubuntu/Debian: sudo apt install pandoc")
        print("- macOS: brew install pandoc")
        sys.exit(1)

    backup = not args.no_backup

    for path in args.paths:
        path_obj = Path(path)

        if path_obj.is_dir():
            if args.recursive:
                convert_recursive(path_obj, backup, args.remove_original)
            else:
                print(f"Skipping directory {path}. Use -r for recursive processing.")
        elif path_obj.is_file():
            convert_file(path_obj, backup, args.remove_original)
        else:
            print(f"Error: {path} is not valid")


if __name__ == "__main__":
    main()
