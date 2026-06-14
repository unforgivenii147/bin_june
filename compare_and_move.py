#!/data/data/com.termux/files/usr/bin/python
import os
import shutil
import sys
from pathlib import Path


def expand_path(path) -> Path:
    """
    Expand user home directory tilde and environment variables.

    Args:
        path: Path string that may contain ~ or environment variables

    Returns:
        Expanded absolute Path object
    """
    # Expand tilde (~) to user home directory
    expanded_path = os.path.expanduser(path)
    # Expand environment variables (e.g., $HOME, ${HOME})
    expanded_path = os.path.expandvars(expanded_path)
    # Convert to absolute path and return as Path object
    return Path(expanded_path).resolve()


def compare_and_move_common(source_dir: str, target_dir: str) -> None:
    """
    Compare two directories and move files that exist in BOTH directories
    from the source directory to a 'common' subdirectory in current dir.

    Args:
        source_dir: Path to first directory (supports ~ and env vars)
        target_dir: Path to second directory (supports ~ and env vars)
    """
    # Expand paths
    source = expand_path(source_dir)
    target = expand_path(target_dir)

    print(f"Source directory (first): {source}")
    print(f"Target directory (second): {target}")
    print("-" * 50)

    # Check if directories exist
    if not source.exists():
        print(f"Error: Source directory '{source_dir}' (expanded to '{source}') does not exist.")
        return
    if not target.exists():
        print(f"Error: Target directory '{target_dir}' (expanded to '{target}') does not exist.")
        return

    # Create 'common' directory in current working directory
    common_dir = Path.cwd() / "common"
    common_dir.mkdir(exist_ok=True)
    print(f"Created/verified directory: {common_dir}")

    # Get files from both directories (only files, not subdirectories)
    source_files = {f.name for f in source.iterdir() if f.is_file()}
    target_files = {f.name for f in target.iterdir() if f.is_file()}

    # Find files that exist in both directories
    common_files = source_files & target_files  # Intersection

    if not common_files:
        print("\nNo files found that exist in both directories.")
        return

    print(f"\nFound {len(common_files)} file(s) that exist in BOTH directories:")
    for filename in sorted(common_files):
        # Show file sizes for comparison
        source_size = (source / filename).stat().st_size
        target_size = (target / filename).stat().st_size
        size_match = "✓" if source_size == target_size else "⚠"
        print(f"  {size_match} {filename} (source: {source_size} bytes, target: {target_size} bytes)")

    # Ask for confirmation before moving
    print("\n" + "=" * 50)
    response = input(f"Move these {len(common_files)} common file(s) from source to '{common_dir}'? (y/n): ").lower()

    if response != "y":
        print("Operation cancelled.")
        return

    # Move the files
    moved_count = 0
    failed_files = []
    size_mismatches = []

    for filename in sorted(common_files):
        source_path = source / filename
        dest_path = common_dir / filename

        # Check if file sizes differ (warning)
        target_path = target / filename
        if source_path.stat().st_size != target_path.stat().st_size:
            size_mismatches.append(filename)

        # Handle filename conflicts in destination
        if dest_path.exists():
            base, ext = os.path.splitext(filename)
            counter = 1
            while dest_path.exists():
                new_name = f"{base}_common{counter}{ext}"
                dest_path = common_dir / new_name
                counter += 1
            print(f"\n  Note: '{filename}' will be renamed to '{dest_path.name}' to avoid conflict")

        try:
            shutil.move(str(source_path), str(dest_path))
            print(f"  ✓ Moved: {filename} -> {dest_path.name}")
            moved_count += 1
        except Exception as e:
            print(f"  ✗ Error moving {filename}: {e}")
            failed_files.append(filename)

    # Summary
    print("\n" + "=" * 50)
    print(f"Summary: Successfully moved {moved_count} of {len(common_files)} common file(s)")

    if size_mismatches:
        print(f"\n⚠ Warning: {len(size_mismatches)} file(s) had different sizes in source vs target:")
        for filename in size_mismatches:
            print(f"  - {filename}")
        print("  (Files were still moved, but verify they are correct versions)")

    if failed_files:
        print(f"\nFailed to move {len(failed_files)} file(s):")
        for filename in failed_files:
            print(f"  - {filename}")

    if moved_count > 0:
        print(f"\nMoved common files are located in: {common_dir}")
        print(f"Note: These files still exist in the target directory: {target}")


def main() -> None:
    # Parse command line arguments
    if len(sys.argv) != 3:
        print("Usage: python compare_dirs.py <source_directory> <target_directory>")
        print("\nWhat this script does:")
        print("  Moves files that exist in BOTH directories from the source directory")
        print("  to a 'common' folder in the current working directory.")
        print("\nExamples:")
        print("  python compare_dirs.py ~/Documents/dir1 /absolute/path/to/dir2")
        print("  python compare_dirs.py ./first_dir ../second_dir")
        print("  python compare_dirs.py $HOME/data1 $PROJECT/data2")
        sys.exit(1)

    source_dir = sys.argv[1]
    target_dir = sys.argv[2]

    compare_and_move_common(source_dir, target_dir)


if __name__ == "__main__":
    main()
