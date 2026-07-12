#!/data/data/com.termux/files/usr/bin/env python
"""
Remove HTML comments (<!-- ... -->) from HTML and CSS files recursively.
Processes files in parallel and updates them in-place.
"""

import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


# Compile regex for HTML comments
# This handles multi-line comments and non-greedy matching
COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)


def remove_comments_from_file(file_path):
    """
    Remove HTML comments from a single file.
    Returns (file_path, was_updated, error_message)
    """
    try:
        # Read file content
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Remove comments
        new_content = COMMENT_PATTERN.sub("", content)

        # Check if any changes were made
        if new_content != content:
            # Write back to file
            with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
                f.write(new_content)
            return (file_path, True, None)
        else:
            return (file_path, False, None)

    except Exception as e:
        return (file_path, False, str(e))


def find_files(directory, extensions=None):
    """
    Recursively find all files with given extensions.
    Default extensions: .html, .htm, .css
    """
    if extensions is None:
        extensions = {".html", ".htm", ".css"}

    directory = Path(directory)
    if not directory.exists():
        raise ValueError(f"Directory {directory} does not exist")

    # Use rglob to recursively find files
    for file_path in directory.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            yield file_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Remove HTML comments from HTML and CSS files recursively.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to process (default: current directory)")
    parser.add_argument(
        "-e",
        "--extensions",
        nargs="+",
        default=[".html", ".htm", ".css"],
        help="File extensions to process (default: .html .htm .css)",
    )
    parser.add_argument(
        "-w", "--workers", type=int, default=None, help="Number of parallel workers (default: CPU count)"
    )

    args = parser.parse_args()

    # Convert extensions to lowercase set
    extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in args.extensions}

    try:
        # Find all files
        files = list(find_files(args.directory, extensions))

        if not files:
            print(f"No files found with extensions: {', '.join(extensions)}")
            return

        print(f"Found {len(files)} files to process")
        print(f"Using {args.workers or os.cpu_count()} workers")
        print("-" * 50)

        # Process files in parallel
        updated_count = 0
        error_count = 0

        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            # Submit all files for processing
            future_to_file = {executor.submit(remove_comments_from_file, file_path): file_path for file_path in files}

            # Process results as they complete
            for future in as_completed(future_to_file):
                file_path, was_updated, error = future.result()
                rel_path = file_path.relative_to(args.directory)

                if error:
                    print(f"❌ ERROR: {rel_path} - {error}")
                    error_count += 1
                elif was_updated:
                    print(f"✓ UPDATED: {rel_path}")
                    updated_count += 1
                # else: silently skip files with no changes

        # Summary
        print("-" * 50)
        print(f"Summary:")
        print(f"  Total files processed: {len(files)}")
        print(f"  Files updated: {updated_count}")
        print(f"  Errors: {error_count}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
