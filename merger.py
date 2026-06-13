#!/data/data/com.termux/files/usr/bin/python

import argparse
from pathlib import Path

from dh import get_random_filename

EXCLUDE_DIRS = {".git", "__pycache__", ".idea", ".vscode", "node_modules", ".env", "venv"}
DEFAULT_OUTPUT_LEN = 8


def read_file(path):
    """Read file content with error handling."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (IOError, OSError, UnicodeDecodeError):
        return None


def collect_files(root, exclude_self=True, output_file=None):
    """Yield all file paths recursively, excluding specified directories."""
    root_path = Path(root).resolve()

    for file_path in root_path.rglob("*"):
        # Skip directories
        if file_path.is_dir():
            continue

        # Check if any parent directory is in EXCLUDE_DIRS
        if any(part in EXCLUDE_DIRS for part in file_path.parts):
            continue

        # Skip output file and self if requested
        if exclude_self:
            if output_file and file_path.resolve() == Path(output_file).resolve():
                continue
            if file_path.name == Path(__file__).name:
                continue

        yield file_path


def write_file_with_markers(fo, file_path, content, include_filename, is_last):
    """Write file content with optional filename marker."""
    if include_filename:
        # Add separator before filename (except for first file)
        fo.write(f"\n{'=' * 60}\n")
        fo.write(f"File: {file_path}\n")
        fo.write(f"{'=' * 60}\n")

    fo.write(content)

    if not is_last:
        fo.write("\n")


def merge_files(root, include_filename=False, output_file=None):
    """Merge all files from root directory into single output file."""
    # Generate output filename if not provided
    if output_file is None:
        output_file = Path(f"{get_random_filename(DEFAULT_OUTPUT_LEN)}.txt")
    else:
        output_file = Path(output_file)

    # Collect all files
    files = list(collect_files(root, exclude_self=True, output_file=output_file))

    if not files:
        print("No files found to merge.")
        return None

    # Write merged content
    try:
        with output_file.open("w", encoding="utf-8") as fo:
            for i, file_path in enumerate(files):
                content = read_file(file_path)
                if content is None:
                    print(f"Warning: Could not read {file_path}")
                    continue

                write_file_with_markers(fo, file_path, content, include_filename, i == len(files) - 1)

        print(f"\n✅ Merged {len(files)} files into: {output_file}")
        return output_file

    except IOError as e:
        print(f"Error writing output file: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Merge files recursively into a single text file", epilog="Example: %(prog)s --path ./src -i"
    )
    parser.add_argument("--path", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument(
        "-i",
        "--include-filename",
        action="store_true",
        help="Include filename as a marker line before each file's content",
    )
    parser.add_argument("-o", "--output", help="Custom output filename (default: random 8 chars + .txt)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed progress information")

    args = parser.parse_args()

    # Validate path
    root_path = Path(args.path)
    if not root_path.exists():
        print(f"Error: Path '{args.path}' does not exist")
        return 1

    if args.verbose:
        print(f"Scanning directory: {root_path.resolve()}")
        print(f"Include filenames: {args.include_filename}")
        print(f"Excluding dirs: {', '.join(EXCLUDE_DIRS)}")

    # Perform merge
    result = merge_files(root_path, args.include_filename, args.output)

    return 0 if result else 1


if __name__ == "__main__":
    exit(main())
