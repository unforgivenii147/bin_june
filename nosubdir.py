#!/data/data/com.termux/files/usr/bin/python
import argparse
import pathlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial


def check_directory(dir_path, max_size_kb=None):
    """
    Check if a directory meets the criteria:
    - Has no subdirectories
    - Contains at least one .py file
    - Total size is under max_size_kb (if specified)

    Returns directory name if it matches, None otherwise
    """
    try:
        contents = list(dir_path.iterdir())

        # Check for subdirectories
        has_subdirs = any(item.is_dir() for item in contents)
        if has_subdirs:
            return None

        # Check for .py files
        py_files = [item for item in contents if item.is_file() and item.suffix == ".py"]
        if not py_files:
            return None

        # Check size if max_size_kb is specified
        if max_size_kb is not None:
            total_size = sum(f.stat().st_size for f in contents if f.is_file()) + sum(
                f.stat().st_size for f in py_files if f.is_file()
            )
            # Convert to KB (1 KB = 1024 bytes)
            total_size_kb = total_size / 1024
            if total_size_kb > max_size_kb:
                return None

        return dir_path.name

    except (PermissionError, OSError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Find top-level directories without subdirs that contain .py files")
    parser.add_argument(
        "-s", "--size", type=float, help="Maximum directory size in KB (e.g., -s 100 for 100KB)", default=None
    )
    args = parser.parse_args()

    current_dir = pathlib.Path(".")

    # Get all top-level directories
    dirs = [item for item in current_dir.iterdir() if item.is_dir()]

    if not dirs:
        print("No directories found in current directory.")
        return

    # Create partial function with the size argument
    check_func = partial(check_directory, max_size_kb=args.size)

    matching_dirs = []

    # Use parallel processing
    with ProcessPoolExecutor() as executor:
        # Submit all directory checks
        future_to_dir = {executor.submit(check_func, d): d for d in dirs}

        # Collect results as they complete
        for future in as_completed(future_to_dir):
            result = future.result()
            if result is not None:
                matching_dirs.append(result)

    # Print results
    if matching_dirs:
        size_info = f" (max {args.size}KB)" if args.size else ""
        print(f"Directories without subdirs containing .py files{size_info}:")
        for dir_name in sorted(matching_dirs):
            print(f"  - {dir_name}")
        print(f"\nTotal: {len(matching_dirs)} directory(ies)")
    else:
        size_info = f" under {args.size}KB" if args.size else ""
        print(f"No matching directories found{size_info}.")


if __name__ == "__main__":
    main()
