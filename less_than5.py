#!/data/data/com.termux/files/usr/bin/env python
import shutil
import time
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

TIME_THRESHOLD = 8 * 60  # 8 minutes in seconds


def get_file_age(filepath: Path) -> float:
    """Get the age of a file in seconds."""
    current_time = time.time()
    file_creation_time = filepath.stat().st_ctime
    return current_time - file_creation_time


def get_unique_filename(dest_dir: Path, filename: str) -> Path:
    """
    Generate a unique filename if the destination already exists.

    Args:
        dest_dir: Destination directory
        filename: Original filename

    Returns:
        Path: Unique file path
    """
    dest_path = dest_dir / filename
    if not dest_path.exists():
        return dest_path

    stem = dest_path.stem
    suffix = dest_path.suffix
    counter = 1

    while True:
        new_filename = f"{stem}_{counter}{suffix}"
        new_path = dest_dir / new_filename
        if not new_path.exists():
            return new_path
        counter += 1


def move_recent_files(start_dir: Path | str = ".") -> None:
    """
    Move files created in the last TIME_THRESHOLD seconds to a '5min' subdirectory.

    Args:
        start_dir: Directory to search for files (default: current directory)
    """
    start_dir = Path(start_dir)
    if not start_dir.is_dir():
        raise ValueError(f"Directory not found: {start_dir}")

    target_dir = start_dir / "5min"
    target_dir.mkdir(exist_ok=True, parents=True)

    moved_count = 0
    skipped_count = 0
    error_count = 0

    # Walk through all files
    for file_path in start_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip files in the target directory
        if target_dir in file_path.parents or file_path.parent == target_dir:
            continue

        try:
            # Check if file is recent
            if get_file_age(file_path) <= TIME_THRESHOLD:
                # Calculate relative path and destination
                rel_path = file_path.parent.relative_to(start_dir)
                dest_dir = target_dir / rel_path if str(rel_path) != "." else target_dir
                dest_dir.mkdir(exist_ok=True, parents=True)

                # Get unique filename if needed
                dest_path = get_unique_filename(dest_dir, file_path.name)

                # Move the file
                shutil.move(str(file_path), str(dest_path))
                print(f"Moved: {file_path.name} -> {dest_path.relative_to(start_dir)}")
                moved_count += 1

        except (OSError, PermissionError) as e:
            print(f"Error processing {file_path.name}: {e}")
            error_count += 1
        except Exception as e:
            print(f"Unexpected error processing {file_path.name}: {e}")
            error_count += 1

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Files moved: {moved_count}")
    print(f"Files skipped: {skipped_count}")
    print(f"Errors: {error_count}")
    print(f"Total processed: {moved_count + skipped_count + error_count}")
    print("=" * 60)


def move_recent_files_with_filters(
    start_dir: Path | str = ".",
    extensions: list[str] | None = None,
    min_size: int | None = None,
    recursive: bool = True,
) -> None:
    """
    Move recent files with additional filters.

    Args:
        start_dir: Directory to search
        extensions: List of extensions to include (e.g., ['.txt', '.log'])
        min_size: Minimum file size in bytes
        recursive: Whether to search recursively
    """
    start_dir = Path(start_dir)
    if not start_dir.is_dir():
        raise ValueError(f"Directory not found: {start_dir}")

    target_dir = start_dir / "5min"
    target_dir.mkdir(exist_ok=True, parents=True)

    # Build file list based on recursion preference
    if recursive:
        files = list(start_dir.rglob("*"))
    else:
        files = [f for f in start_dir.iterdir() if f.is_file()]

    moved_count = 0
    filtered_count = 0

    for file_path in files:
        if not file_path.is_file():
            continue

        # Skip files in target directory
        if target_dir in file_path.parents or file_path.parent == target_dir:
            continue

        # Apply filters
        if extensions and file_path.suffix.lower() not in extensions:
            filtered_count += 1
            continue

        if min_size and file_path.stat().st_size < min_size:
            filtered_count += 1
            continue

        try:
            if get_file_age(file_path) <= TIME_THRESHOLD:
                # Calculate destination
                rel_path = file_path.parent.relative_to(start_dir)
                dest_dir = target_dir / rel_path if str(rel_path) != "." else target_dir
                dest_dir.mkdir(exist_ok=True, parents=True)

                # Handle duplicates
                dest_path = get_unique_filename(dest_dir, file_path.name)

                # Move file
                shutil.move(str(file_path), str(dest_path))
                print(f"Moved: {file_path.name} -> {dest_path.relative_to(start_dir)}")
                moved_count += 1

        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

    print(f"\nMoved {moved_count} files ({filtered_count} filtered out)")


def move_recent_files_by_age(
    start_dir: Path | str = ".", age_threshold: int = TIME_THRESHOLD, destination: str = "old_files"
) -> None:
    """
    Move files older than a certain age instead of recent ones.

    Args:
        start_dir: Directory to search
        age_threshold: Age threshold in seconds
        destination: Name of destination directory
    """
    start_dir = Path(start_dir)
    if not start_dir.is_dir():
        raise ValueError(f"Directory not found: {start_dir}")

    target_dir = start_dir / destination
    target_dir.mkdir(exist_ok=True, parents=True)

    moved_count = 0

    for file_path in start_dir.rglob("*"):
        if not file_path.is_file():
            continue

        if target_dir in file_path.parents or file_path.parent == target_dir:
            continue

        try:
            if get_file_age(file_path) > age_threshold:
                rel_path = file_path.parent.relative_to(start_dir)
                dest_dir = target_dir / rel_path if str(rel_path) != "." else target_dir
                dest_dir.mkdir(exist_ok=True, parents=True)

                dest_path = get_unique_filename(dest_dir, file_path.name)
                shutil.move(str(file_path), str(dest_path))
                print(f"Moved (old): {file_path.name} -> {dest_path.relative_to(start_dir)}")
                moved_count += 1

        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

    print(f"\nMoved {moved_count} old files to {destination}/")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Move files created in the last N minutes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python move_recent_files.py                    # Move files from last 8 minutes
  python move_recent_files.py --minutes 5        # Move files from last 5 minutes
  python move_recent_files.py --ext .txt .log    # Only move .txt and .log files
  python move_recent_files.py --min-size 1024    # Only move files > 1KB
  python move_recent_files.py --non-recursive    # Don't search subdirectories
  python move_recent_files.py --old              # Move old files instead
  python move_recent_files.py --dest archive     # Use custom destination name
        """,
    )
    parser.add_argument("--dir", default=".", help="Directory to process (default: current directory)")
    parser.add_argument("--minutes", type=int, default=8, help="Age threshold in minutes (default: 8)")
    parser.add_argument("--ext", nargs="+", help="File extensions to include (e.g., .txt .log)")
    parser.add_argument("--min-size", type=int, help="Minimum file size in bytes")
    parser.add_argument("--non-recursive", action="store_true", help="Don't search subdirectories")
    parser.add_argument("--old", action="store_true", help="Move old files instead of recent ones")
    parser.add_argument("--dest", default="5min", help="Destination directory name (default: 5min)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    try:
        start_dir = Path(args.dir).resolve()
        print(f"Starting from directory: {start_dir}")
        print(f"Processing files {'older than' if args.old else 'created in the last'} {args.minutes} minutes")
        print("-" * 60)

        # Use the appropriate function based on arguments
        if args.old:
            move_recent_files_by_age(start_dir, age_threshold=args.minutes * 60, destination=args.dest)
        elif args.ext or args.min_size:
            move_recent_files_with_filters(
                start_dir,
                extensions=[ext if ext.startswith(".") else f".{ext}" for ext in (args.ext or [])],
                min_size=args.min_size,
                recursive=not args.non_recursive,
            )
        else:
            # Override the default threshold if minutes is specified
            global TIME_THRESHOLD
            TIME_THRESHOLD = args.minutes * 60
            move_recent_files(start_dir)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
