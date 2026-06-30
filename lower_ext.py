#!/data/data/com.termux/files/usr/bin/python


"""
Find files with uppercase extensions in current directory recursively.
Optionally convert them to lowercase using -a or --autofix flag.
"""

import argparse
import sys
from pathlib import Path


def find_uppercase_extensions(directory: Path, autofix: bool = False):
    uppercase_files = []
    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix:
            extension = file_path.suffix[1:]
            if any((c.isupper() for c in extension)):
                uppercase_files.append(file_path)
                if autofix:
                    new_extension = "." + extension.lower()
                    new_path = file_path.with_suffix(new_extension)
                    try:
                        file_path.rename(new_path)
                        print(f"✓ Renamed: {file_path.name} → {new_path.name}")
                    except Exception as e:
                        print(f"✗ Failed to rename {file_path.name}: {e}", file=sys.stderr)
    return uppercase_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find files with uppercase extensions in current directory recursively"
    )
    parser.add_argument("-a", "--autofix", action="store_true", help="Convert uppercase extensions to lowercase")
    args = parser.parse_args()
    search_dir = Path.cwd()
    print(f"Searching for files with uppercase extensions in: {search_dir}")
    print("=" * 60)
    uppercase_files = find_uppercase_extensions(search_dir, args.autofix)
    if uppercase_files:
        if not args.autofix:
            print(f"\nFound {len(uppercase_files)} file(s) with uppercase extensions:")
            for file_path in uppercase_files:
                print(f"  • {file_path.relative_to(search_dir)} (extension: .{file_path.suffix[1:]})")
            print("\nRun with -a or --autofix to convert them to lowercase")
        else:
            print(f"\n✓ Processed {len(uppercase_files)} file(s)")
    else:
        print("\n✓ No files with uppercase extensions found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
