#!/data/data/com.termux/files/usr/bin/python

import subprocess
import sys
from pathlib import Path


def copy_lines_to_clipboard(filename: str, start_line: int, end_line: (int | None) = None) -> None:
    input_file = Path(filename)
    if not input_file.is_file():
        print(f"Error: File not found at '{filename}'", file=sys.stderr)
        sys.exit(1)
    try:
        with input_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"Error reading file '{filename}': {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while reading the file: {e}", file=sys.stderr)
        sys.exit(1)
    total_lines = len(lines)
    start_index = start_line - 1
    end_index = total_lines if end_line is None else end_line
    if not 0 <= start_index < total_lines:
        print(f"Error: Start line ({start_line}) is out of bounds. File has {total_lines} lines.", file=sys.stderr)
        sys.exit(1)
    if not 0 <= end_index <= total_lines:
        print(
            f"Error: End line ({end_line if end_line is not None else 'end of file'}) is out of bounds. File has {total_lines} lines.",
            file=sys.stderr,
        )
        sys.exit(1)
    if start_index >= end_index:
        print(
            f"Error: Start line ({start_line}) must be before or equal to end line ({end_line if end_line is not None else total_lines}).",
            file=sys.stderr,
        )
        sys.exit(1)
    selected_lines = lines[start_index:end_index]
    content_to_copy = "".join(selected_lines)
    if not content_to_copy:
        print("No content selected to copy.", file=sys.stderr)
        sys.exit(0)
    try:
        process = subprocess.Popen(["termux-clipboard-set"], stdin=subprocess.PIPE, text=True, stderr=subprocess.PIPE)
        _stdout, stderr = process.communicate(input=content_to_copy)
        if process.returncode != 0:
            print(f"Error: Failed to copy to clipboard. STDERR: {stderr}", file=sys.stderr)
            sys.exit(1)
        print(
            f"Successfully copied lines {start_line} to {end_line if end_line is not None else 'end'} of '{filename}' to clipboard."
        )
    except FileNotFoundError:
        print("Error: 'termux-clipboard-set' command not found. Is Termux:API installed?", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while copying to clipboard: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print(f"Usage: {sys.argv[0]} <filename> <start_line> [end_line]", file=sys.stderr)
        print("  <filename>: Path to the input file.", file=sys.stderr)
        print("  <start_line>: The first line number to copy (1-based index).", file=sys.stderr)
        print(
            "  [end_line]: The last line number to copy (1-based index). If omitted, copies to the end of the file.",
            file=sys.stderr,
        )
        sys.exit(1)
    filename = sys.argv[1]
    try:
        start_line = int(sys.argv[2])
    except ValueError:
        print("Error: <start_line> must be an integer.", file=sys.stderr)
        sys.exit(1)
    end_line = None
    if len(sys.argv) == 4:
        try:
            end_line = int(sys.argv[3])
        except ValueError:
            print("Error: <end_line> must be an integer.", file=sys.stderr)
            sys.exit(1)
    copy_lines_to_clipboard(filename, start_line, end_line)


if __name__ == "__main__":
    main()
