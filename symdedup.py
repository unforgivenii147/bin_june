#!/data/data/com.termux/files/usr/bin/env python
"""
Symlink duplicate files recursively with reverse functionality.
Excludes git repos, bin, and site-packages directories.
"""

import argparse
import hashlib
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
from typing import Dict, List, Tuple
import sys


def is_excluded_path(path: Path) -> bool:
    """Check if path should be excluded from processing."""
    parts = path.parts

    # Exclude git repositories
    if ".git" in parts:
        return True

    # Exclude bin and site-packages directories
    if any(part in ("bin", "site-packages") for part in parts):
        return True

    return False


def hash_file(file_path: Path, chunk_size: int = 65536) -> str:
    """Calculate SHA256 hash of file."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError) as e:
        print(f"Warning: Could not hash {file_path}: {e}", file=sys.stderr)
        return None


def collect_files(start_path: Path = Path.cwd()) -> List[Path]:
    """Recursively collect all files, excluding specified directories."""
    files = []

    try:
        for item in start_path.rglob("*"):
            if is_excluded_path(item):
                continue
            if item.is_file() and not item.is_symlink():
                files.append(item)
    except (OSError, PermissionError) as e:
        print(f"Warning: Error scanning directory: {e}", file=sys.stderr)

    return files


def find_duplicates(files: List[Path]) -> Dict[str, List[Path]]:
    """Find duplicate files using parallel hashing."""
    hash_map = defaultdict(list)

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_file = {executor.submit(hash_file, file_path): file_path for file_path in files}

        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                file_hash = future.result()
                if file_hash:
                    hash_map[file_hash].append(file_path)
            except Exception as e:
                print(f"Error processing {file_path}: {e}", file=sys.stderr)

    # Return only groups with duplicates (2+ files)
    return {h: files for h, files in hash_map.items() if len(files) > 1}


def create_symlinks(duplicate_groups: Dict[str, List[Path]]) -> Tuple[int, int]:
    """Create symlinks for duplicate files. Keep first as original."""
    symlink_count = 0
    error_count = 0

    for file_hash, file_list in duplicate_groups.items():
        # Sort by path for consistent behavior
        file_list.sort()
        original = file_list[0]

        for duplicate in file_list[1:]:
            try:
                # Calculate relative path from symlink to original
                rel_path = Path(original).relative_to(duplicate.parent.parent)

                # Try various relative path strategies
                try:
                    rel_path = original.relative_to(duplicate.parent)
                except ValueError:
                    # If in different branches, use absolute path
                    rel_path = original.resolve()

                # Remove the duplicate file
                duplicate.unlink()

                # Create symlink
                duplicate.symlink_to(rel_path)
                symlink_count += 1
                print(f"✓ Symlinked: {duplicate} → {original}")

            except (OSError, PermissionError) as e:
                error_count += 1
                print(f"✗ Failed to symlink {duplicate}: {e}", file=sys.stderr)

    return symlink_count, error_count


def restore_symlinks(start_path: Path = Path.cwd()) -> Tuple[int, int]:
    """Replace symlinks with original file copies (reverse functionality)."""
    restored_count = 0
    error_count = 0

    try:
        for symlink_path in start_path.rglob("*"):
            if is_excluded_path(symlink_path):
                continue

            if symlink_path.is_symlink():
                try:
                    target = symlink_path.resolve()

                    # Verify target exists
                    if not target.exists():
                        print(f"✗ Target not found for {symlink_path}", file=sys.stderr)
                        error_count += 1
                        continue

                    # Remove symlink and copy original file
                    symlink_path.unlink()
                    shutil.copy2(target, symlink_path)
                    restored_count += 1
                    print(f"✓ Restored: {symlink_path} (copied from {target})")

                except (OSError, PermissionError) as e:
                    error_count += 1
                    print(f"✗ Failed to restore {symlink_path}: {e}", file=sys.stderr)

    except (OSError, PermissionError) as e:
        print(f"Warning: Error scanning for symlinks: {e}", file=sys.stderr)

    return restored_count, error_count


def main():
    parser = argparse.ArgumentParser(description="Symlink duplicate files recursively with reverse functionality")
    parser.add_argument(
        "-r", "--reverse", action="store_true", help="Replace symlinks with original files (restore duplicates)"
    )
    parser.add_argument(
        "-d", "--directory", type=Path, default=Path.cwd(), help="Directory to process (default: current directory)"
    )

    args = parser.parse_args()

    print(f"Processing directory: {args.directory.resolve()}")

    if args.reverse:
        print("\n🔄 Reverse mode: restoring files from symlinks...\n")
        restored, errors = restore_symlinks(args.directory)
        print(f"\n✓ Restored: {restored} files")
        if errors:
            print(f"✗ Errors: {errors}")
    else:
        print("\n🔍 Scanning for files...\n")
        files = collect_files(args.directory)
        print(f"Found {len(files)} files\n")

        print("🔗 Finding duplicates...\n")
        duplicates = find_duplicates(files)

        if not duplicates:
            print("No duplicate files found.")
            return

        total_duplicates = sum(len(group) - 1 for group in duplicates.values())
        print(f"Found {len(duplicates)} duplicate groups ({total_duplicates} duplicate files)\n")

        print("📎 Creating symlinks...\n")
        symlinked, errors = create_symlinks(duplicates)
        print(f"\n✓ Symlinked: {symlinked} files")
        if errors:
            print(f"✗ Errors: {errors}")


if __name__ == "__main__":
    main()
