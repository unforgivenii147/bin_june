#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from dh.fileutils import unique_path
from dh.fileutils import _clean_fname
from dh.fileutils import should_skip

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def remove_string_from_names(
    string_to_remove: str,
    dry_run: bool = False,
    recursive: bool = False,
    current_path: Path = Path.cwd(),
) -> int:
    renamed_count = 0
    try:
        items = current_path.iterdir()
    except PermissionError:
        print(f"Permission denied: {current_path}")
        return renamed_count

    for item in items:
        if should_skip(item):
            continue

        if (item.is_file() or item.is_dir()) and string_to_remove in item.name:
            new_name = item.name.replace(string_to_remove, "")
            if not new_name.strip():
                print(f"Warning: Removing '{string_to_remove}' would make name empty for '{item.name}'")
                continue

            new_path = current_path / new_name
            if new_path.exists():
                new_path = unique_path(new_path)

            if dry_run:
                print(f"[DRY RUN] Would rename: {item} -> {new_name}")
            else:
                try:
                    item.rename(new_path)
                    print(f"{item} -> {new_name}")
                    renamed_count += 1
                except OSError as e:
                    print(f"Error renaming '{item.name}': {e}")

        if recursive and item.is_dir():
            renamed_count += remove_string_from_names(string_to_remove, dry_run, recursive, item)

    return renamed_count


def replace_string_in_names(
    str1: str,
    str2: str,
    dry_run: bool = False,
    recursive: bool = False,
    current_path: Path = Path.cwd(),
) -> int:
    renamed_count = 0
    try:
        items = current_path.iterdir()
    except PermissionError:
        print(f"Permission denied: {current_path}")
        return renamed_count

    for item in items:
        if should_skip(item):
            continue

        if (item.is_file() or item.is_dir()) and str1 in item.name:
            new_name = item.name.replace(str1, str2)
            if not new_name.strip():
                print(f"Warning: Replacing '{str1}' with '{str2}' would make name empty for '{item.name}'")
                continue

            new_path = current_path / new_name
            if new_path.exists():
                new_path = unique_path(new_path)

            if dry_run:
                print(f"[DRY RUN] Would rename: {item} -> {new_name}")
            else:
                try:
                    item.rename(new_path)
                    print(f"{item} -> {new_name}")
                    renamed_count += 1
                except OSError as e:
                    print(f"Error renaming '{item.name}': {e}")

        if recursive and item.is_dir():
            renamed_count += replace_string_in_names(str1, str2, dry_run, recursive, item)

    return renamed_count


def rename_by_template(
    template: str, dry_run: bool = False, recursive: bool = False, current_path: Path = Path.cwd()
) -> int:
    renamed_count = 0

    try:
        files = [f for f in current_path.iterdir() if f.is_file() and not should_skip(f)]

        script_name = Path(__file__).name
        files = [f for f in files if f.name != script_name]

        if files:
            file_count = len(files)
            if file_count < 10:
                padding = 1
            elif file_count < 100:
                padding = 2
            elif file_count < 1000:
                padding = 3
            else:
                padding = 4

            for i, file_path in enumerate(sorted(files), 1):
                _name, ext = file_path.stem, file_path.suffix
                number_str = str(i).zfill(padding)
                new_name = f"{template}{number_str}{ext}"

                if new_name == file_path.name:
                    continue

                new_path = current_path / new_name
                if new_path.exists():
                    new_path = unique_path(new_path)

                if dry_run:
                    print(f"[DRY RUN] Would rename: {file_path.name} -> {new_name}")
                else:
                    try:
                        file_path.rename(new_path)
                        print(f"{file_path.name} -> {new_name}")
                        renamed_count += 1
                    except OSError as e:
                        print(f"Error renaming '{file_path.name}': {e}")

    except PermissionError:
        print(f"Permission denied: {current_path}")
        return renamed_count

    if recursive:
        try:
            for item in current_path.iterdir():
                if item.is_dir() and not should_skip(item):
                    renamed_count += rename_by_template(template, dry_run, recursive, item)
        except PermissionError:
            print(f"Permission denied accessing subdirectory in {current_path}")

    return renamed_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rename files and directories using pathlib",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
  Examples:
  python pnr.py -r "old_string"
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-r",
        "--remove",
        metavar="STRING",
        help="Remove specified string from file and directory names",
    )
    group.add_argument(
        "-s",
        "--replace",
        nargs=2,
        metavar=("STR1", "STR2"),
        help="Replace STR1 with STR2 in file and directory names",
    )
    group.add_argument(
        "-t",
        "--template",
        metavar="NAME",
        help="Rename files using template with sequential numbering",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be renamed without actually doing it",
    )
    parser.add_argument("--recursive", action="store_true", help="Process directories recursively")
    args = parser.parse_args()

    cwd = Path.cwd()
    print(f"Working in directory: {cwd}")
    if args.recursive:
        print("Recursive mode enabled")
    if args.dry_run:
        print("DRY RUN MODE - No actual changes will be made\n")

    try:
        if args.remove:
            print(f"Removing '{args.remove}' from names...")
            count = remove_string_from_names(args.remove, args.dry_run, args.recursive)
            print(f"\nOperation completed. {count} items processed.")
        elif args.replace:
            str1, str2 = args.replace
            print(f"Replacing '{str1}' with '{str2}' in names...")
            count = replace_string_in_names(str1, str2, args.dry_run, args.recursive)
            print(f"\nOperation completed. {count} items processed.")
        elif args.template:
            print(f"Renaming files using template '{args.template}'...")
            count = rename_by_template(args.template, args.dry_run, args.recursive)
            print(f"\nOperation completed. {count} items processed.")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
