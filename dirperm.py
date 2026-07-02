#!/data/data/com.termux/files/usr/bin/env python
import os
import stat
from pathlib import Path
from tqdm import tqdm
import argparse

# Global skip directories
SKIP_DIRS = {".git", ".ruff_cache", "__pycache__"}


def should_skip_dir(dirname):
    """Check if directory should be skipped"""
    return dirname in SKIP_DIRS


def walk_all(root_path="."):
    """Generator that yields all directories and files recursively, skipping specified directories"""
    for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
        # Filter out directories to skip in-place
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

        # Yield the directory itself
        yield "dir", dirpath

        # Yield files in this directory
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)

            # Skip symlinks
            if os.path.islink(filepath):
                continue

            yield "file", filepath


def walk_dirs(root_path="."):
    """Generator that yields only directories recursively, skipping specified directories"""
    for item_type, path in walk_all(root_path):
        if item_type == "dir":
            yield path


def walk_files(root_path="."):
    """Generator that yields only files recursively, skipping specified directories"""
    for item_type, path in walk_all(root_path):
        if item_type == "file":
            yield path


def has_shebang(filepath):
    """Check if file has a shebang (#!) on the first line"""
    try:
        with open(filepath, "rb") as f:
            first_line = f.readline()
            return first_line.startswith(b"#!")
    except (OSError, IOError):
        return False


def is_executable(path):
    """Check if file/directory is currently executable"""
    try:
        return os.access(path, os.X_OK)
    except:
        return False


def get_current_mode(path):
    """Get current permissions mode"""
    try:
        return stat.S_IMODE(os.stat(path).st_mode)
    except:
        return None


def determine_dir_target_mode(dirpath):
    """
    Determine target permissions for directories:
    - Directories should be 0775
    """
    return 0o775


def determine_file_target_mode(filepath):
    """
    Determine target permissions based on rules:
    - If file is executable: don't change permissions (returns None)
    - If file has shebang or parent dir is 'bin': make executable (0755)
    - Otherwise: set to 0644
    """
    if is_executable(filepath):
        return None

    parent_dir = os.path.basename(os.path.dirname(filepath))
    if has_shebang(filepath) or parent_dir == "bin":
        return 0o755

    return 0o644


def analyze_item(item_type, path):
    """
    Analyze a single item and return its status.
    Returns: (status, path, current_mode, target_mode)
    """
    if item_type == "dir":
        target_mode = determine_dir_target_mode(path)
    else:  # file
        target_mode = determine_file_target_mode(path)

    # Skip executable files
    if target_mode is None:
        return ("skip_executable", path, None, None)

    current_mode = get_current_mode(path)
    if current_mode is None:
        return ("error", path, None, target_mode)

    if current_mode != target_mode:
        return ("change", path, current_mode, target_mode)
    else:
        return ("skip_correct", path, current_mode, target_mode)


def process_item(path, target_mode, dry_run=False):
    """Process a single item - change permissions or simulate"""
    if dry_run:
        return True

    try:
        os.chmod(path, target_mode)
        return True
    except Exception as e:
        print(f"Error: {path}: {e}")
        return False


def scan_and_report(root_path="."):
    """Scan all items and report what would be changed"""
    stats = {
        "total_dirs": 0,
        "total_files": 0,
        "dirs_to_change": [],
        "dirs_correct": [],
        "files_skip_executable": [],
        "files_skip_correct": [],
        "files_make_executable": [],
        "files_set_standard": [],
        "errors": [],
    }

    print("Scanning directories and files...")
    all_items = walk_all(root_path)

    # Wrap with tqdm for progress during scanning
    for item_type, path in tqdm(all_items, desc="Analyzing", unit="items"):
        if item_type == "dir":
            stats["total_dirs"] += 1
        else:
            stats["total_files"] += 1

        status, path, current, target = analyze_item(item_type, path)

        if status == "skip_executable":
            stats["files_skip_executable"].append(path)
        elif status == "skip_correct":
            if item_type == "dir":
                stats["dirs_correct"].append(path)
            else:
                stats["files_skip_correct"].append(path)
        elif status == "change":
            if item_type == "dir":
                stats["dirs_to_change"].append((path, current, target))
            else:
                if target == 0o755:
                    stats["files_make_executable"].append((path, current, target))
                else:
                    stats["files_set_standard"].append((path, current, target))
        elif status == "error":
            stats["errors"].append(path)

    return stats


def apply_changes(stats, dry_run=False):
    """Apply permission changes with progress bar"""
    all_changes = stats["dirs_to_change"] + stats["files_make_executable"] + stats["files_set_standard"]

    if not all_changes:
        print("\nNo changes needed!")
        return 0, 0

    print(f"\nApplying changes to {len(all_changes)} items...")

    success = 0
    failed = 0

    for path, current, target in tqdm(all_changes, desc="Changing permissions", unit="items"):
        if process_item(path, target, dry_run):
            success += 1
        else:
            failed += 1

    return success, failed


def print_report(stats, success=None, failed=None):
    """Print detailed report of what was done"""
    total_items = stats["total_dirs"] + stats["total_files"]
    total_changes = (
        len(stats["dirs_to_change"]) + len(stats["files_make_executable"]) + len(stats["files_set_standard"])
    )

    print(f"\n{'=' * 60}")
    print(f"Scan Summary:")
    print(f"  Total items scanned: {total_items}")
    print(f"    Directories: {stats['total_dirs']}")
    print(f"    Files: {stats['total_files']}")
    print(f"\nDirectory Permissions:")
    print(f"  → Will set to 0775: {len(stats['dirs_to_change'])}")
    print(f"  ✓ Already correct (0775): {len(stats['dirs_correct'])}")
    print(f"\nFile Permissions:")
    print(f"  ⊘ Already executable (skipped): {len(stats['files_skip_executable'])}")
    print(f"  → Will make executable (+x): {len(stats['files_make_executable'])}")
    print(f"  → Will set to standard (0644): {len(stats['files_set_standard'])}")
    print(f"  ✓ Already correct: {len(stats['files_skip_correct'])}")
    print(f"\nTotal changes needed: {total_changes}")

    if stats["errors"]:
        print(f"  ✗ Errors during analysis: {len(stats['errors'])}")

    if success is not None:
        print(f"\n{'=' * 60}")
        print(f"Results:")
        print(f"  ✓ Changes successful: {success}")
        if failed:
            print(f"  ✗ Changes failed: {failed}")

    print(f"{'=' * 60}")


def show_examples(stats, num=5):
    """Show examples of files/directories in each category"""
    if stats["dirs_to_change"]:
        print(f"\nExamples of directories to change to 0775:")
        for path, current, target in stats["dirs_to_change"][:num]:
            print(f"  {oct(current)} -> {oct(target)}  {path}")
        if len(stats["dirs_to_change"]) > num:
            print(f"  ... and {len(stats['dirs_to_change']) - num} more")

    if stats["files_make_executable"]:
        print(f"\nExamples of files to make executable (+x):")
        for path, current, target in stats["files_make_executable"][:num]:
            print(f"  {oct(current)} -> {oct(target)}  {path}")
        if len(stats["files_make_executable"]) > num:
            print(f"  ... and {len(stats['files_make_executable']) - num} more")

    if stats["files_set_standard"]:
        print(f"\nExamples of files to set to 0644:")
        for path, current, target in stats["files_set_standard"][:num]:
            print(f"  {oct(current)} -> {oct(target)}  {path}")
        if len(stats["files_set_standard"]) > num:
            print(f"  ... and {len(stats['files_set_standard']) - num} more")

    if stats["files_skip_executable"]:
        print(f"\nExamples of skipped files (already executable):")
        for path in stats["files_skip_executable"][:num]:
            print(f"  {path}")
        if len(stats["files_skip_executable"]) > num:
            print(f"  ... and {len(stats['files_skip_executable']) - num} more")


def main():
    parser = argparse.ArgumentParser(
        description="Fix directory and file permissions with smart rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Rules for directories:
  - All directories: set to 0775 (rwxrwxr-x)

Rules for files:
  - Files that are already executable: no changes
  - Files with shebang (#!) or in 'bin' directory: set to 0755 (rwxr-xr-x)
  - All other files: set to 0644 (rw-r--r--)

Skipped directories: {", ".join(sorted(SKIP_DIRS))}

Examples:
  %(prog)s                    # Process current directory
  %(prog)s /path/to/project   # Process specific path
  %(prog)s . --dry-run        # Preview changes
  %(prog)s . --show-examples  # Show examples of changes
  %(prog)s . --dirs-only      # Only process directories
  %(prog)s . --files-only     # Only process files
        """,
    )
    parser.add_argument("path", nargs="?", default=".", help="Root path to start from (default: current directory)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without actually changing permissions"
    )
    parser.add_argument(
        "--show-examples", action="store_true", help="Show example files/directories that would be changed"
    )
    parser.add_argument("--dirs-only", action="store_true", help="Only process directories, skip files")
    parser.add_argument("--files-only", action="store_true", help="Only process files, skip directories")

    args = parser.parse_args()

    print(f"Skip directories: {', '.join(sorted(SKIP_DIRS))}")
    if args.dirs_only:
        print("Mode: Directories only")
    elif args.files_only:
        print("Mode: Files only")

    if args.dry_run:
        print("DRY RUN - No changes will be made\n")

    # Scan all items using generator
    if args.dirs_only:
        print("Scanning directories...")
        dirs = list(tqdm(walk_dirs(args.path), desc="Scanning dirs", unit="dirs"))
        items = [("dir", d) for d in dirs]
    elif args.files_only:
        print("Scanning files...")
        files = list(tqdm(walk_files(args.path), desc="Scanning files", unit="files"))
        items = [("file", f) for f in files]
    else:
        items = walk_all(args.path)

    # Process items
    stats = {
        "total_dirs": 0,
        "total_files": 0,
        "dirs_to_change": [],
        "dirs_correct": [],
        "files_skip_executable": [],
        "files_skip_correct": [],
        "files_make_executable": [],
        "files_set_standard": [],
        "errors": [],
    }

    # Wrap with tqdm for progress
    item_list = list(items) if not isinstance(items, list) else items
    for item_type, path in tqdm(item_list, desc="Analyzing", unit="items"):
        if item_type == "dir":
            stats["total_dirs"] += 1
        else:
            stats["total_files"] += 1

        status, path, current, target = analyze_item(item_type, path)

        if status == "skip_executable":
            stats["files_skip_executable"].append(path)
        elif status == "skip_correct":
            if item_type == "dir":
                stats["dirs_correct"].append(path)
            else:
                stats["files_skip_correct"].append(path)
        elif status == "change":
            if item_type == "dir":
                stats["dirs_to_change"].append((path, current, target))
            else:
                if target == 0o755:
                    stats["files_make_executable"].append((path, current, target))
                else:
                    stats["files_set_standard"].append((path, current, target))
        elif status == "error":
            stats["errors"].append(path)

    # Print report
    print_report(stats)

    # Show examples if requested
    if args.show_examples:
        show_examples(stats)

    # Apply changes
    if not args.dry_run:
        success, failed = apply_changes(stats, dry_run=False)
        if success is not None:
            print(f"\n{'=' * 60}")
            print(f"Final Results:")
            print(f"  ✓ Changes applied successfully: {success}")
            if failed:
                print(f"  ✗ Failed changes: {failed}")
            print(f"{'=' * 60}")
    else:
        total_changes = (
            len(stats["dirs_to_change"]) + len(stats["files_make_executable"]) + len(stats["files_set_standard"])
        )
        if total_changes > 0:
            print(f"\nWould apply {total_changes} changes")


if __name__ == "__main__":
    main()
