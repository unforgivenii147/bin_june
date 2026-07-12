#!/data/data/com.termux/files/usr/bin/env python
"""
TOML Comment Remover - Removes comments from TOML files using parallel processing.
Supports processing multiple files/directories recursively.
"""

import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple


def remove_toml_comments(content: str) -> str:
    """
    Remove comments from TOML content while preserving strings.
    Handles both inline (#) comments and respects TOML string literals.
    """
    lines = content.splitlines(keepends=True)
    result_lines = []
    in_multiline_string = False
    multiline_string_delimiter = ""

    for line in lines:
        # Handle multiline strings (triple quotes)
        if '"""' in line or "'''" in line:
            # Find triple quote positions
            dbl_triple = line.find('"""')
            sgl_triple = line.find("'''")

            if not in_multiline_string:
                # Check if we're entering a multiline string
                if dbl_triple != -1 or sgl_triple != -1:
                    in_multiline_string = True
                    if dbl_triple != -1:
                        multiline_string_delimiter = '"""'
                    else:
                        multiline_string_delimiter = "'''"
                    result_lines.append(line)
                    # Check if multiline string ends on same line
                    count = line.count(multiline_string_delimiter)
                    if count >= 2:
                        in_multiline_string = False
                else:
                    # Normal line - remove comments
                    result_lines.append(remove_line_comment(line))
            else:
                # We're inside a multiline string
                result_lines.append(line)
                if multiline_string_delimiter in line:
                    # Check if this line ends the multiline string
                    count = line.count(multiline_string_delimiter)
                    if in_multiline_string and count >= 1:
                        in_multiline_string = False
        else:
            if not in_multiline_string:
                result_lines.append(remove_line_comment(line))
            else:
                result_lines.append(line)

    return "".join(result_lines)


def remove_line_comment(line: str) -> str:
    """
    Remove inline comments from a single line, respecting quoted strings.
    """
    result = []
    in_string = False
    string_char = None
    i = 0

    while i < len(line):
        char = line[i]

        # Handle string boundaries
        if char in ('"', "'") and (i == 0 or line[i - 1] != "\\"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None

        # Found a comment character outside of string
        if char == "#" and not in_string:
            # Check if it's really a comment (not part of a value)
            # Look backwards to see if we have only whitespace before this
            before_comment = line[:i].rstrip()
            if not before_comment or before_comment[-1] in "=[{, \t":
                break

        result.append(char)
        i += 1

    # Join result and preserve trailing newline if present
    result_line = "".join(result)
    if result_line.rstrip() == "" and line.strip() == "":
        return "\n" if line.endswith("\n") else ""

    # Preserve the newline character
    if line.endswith("\n"):
        return result_line.rstrip() + "\n"
    return result_line.rstrip()


def process_file(file_path: Path) -> Tuple[str, float, int, int]:
    """
    Process a single TOML file to remove comments.
    Returns: (filename, time_taken_ms, before_size, after_size)
    """
    start_time = time.perf_counter()

    try:
        # Read the file
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        before_size = len(content.encode("utf-8"))

        # Remove comments
        cleaned_content = remove_toml_comments(content)

        # Write back to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(cleaned_content)

        after_size = len(cleaned_content.encode("utf-8"))

        time_taken = (time.perf_counter() - start_time) * 1000  # Convert to milliseconds

        return (str(file_path), time_taken, before_size, after_size)

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        time_taken = (time.perf_counter() - start_time) * 1000
        return (str(file_path), time_taken, 0, 0)


def collect_toml_files(paths: List[Path]) -> List[Path]:
    """
    Collect all .toml files from given paths. Directories are scanned recursively.
    """
    toml_files = []

    for path in paths:
        if path.is_file():
            if path.suffix.lower() == ".toml":
                toml_files.append(path)
        elif path.is_dir():
            toml_files.extend(path.rglob("*.toml"))

    return toml_files


def format_size(size_bytes: int) -> str:
    """Format byte size to human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def main():
    # Parse command line arguments
    if len(sys.argv) > 1:
        paths = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Default: process current directory recursively
        paths = [Path.cwd()]

    # Collect all TOML files
    toml_files = collect_toml_files(paths)

    if not toml_files:
        print("No .toml files found to process.")
        return

    print(f"Found {len(toml_files)} TOML file(s) to process...")
    print("-" * 80)
    print(f"{'Filename':<50} {'Time (ms)':<10} {'Before':<12} {'After':<12} {'Ratio':<8}")
    print("-" * 80)

    # Process files in parallel
    max_workers = min(len(toml_files), 8)  # Use up to 8 workers
    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_file, file): file for file in toml_files}

        # Process completed tasks
        for future in as_completed(future_to_file):
            result = future.result()
            results.append(result)

            # Display result immediately
            filename, time_taken, before_size, after_size = result
            ratio = (after_size / before_size * 100) if before_size > 0 else 0

            # Truncate filename for display
            display_name = filename if len(filename) <= 48 else "..." + filename[-45:]

            print(
                f"{display_name:<50} {time_taken:>8.2f}  "
                f"{format_size(before_size):<12} {format_size(after_size):<12} "
                f"{ratio:>6.1f}%"
            )

    # Summary statistics
    print("-" * 80)
    total_before = sum(r[2] for r in results)
    total_after = sum(r[3] for r in results)
    total_ratio = (total_after / total_before * 100) if total_before > 0 else 0
    total_time = sum(r[1] for r in results)

    print(f"Total: {len(results)} file(s) processed in {total_time:.2f} ms")
    print(f"Size reduction: {format_size(total_before)} -> {format_size(total_after)} ({total_ratio:.1f}% of original)")


if __name__ == "__main__":
    main()
