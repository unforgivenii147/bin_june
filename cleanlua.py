#!/data/data/com.termux/files/usr/bin/env python
"""
Strip comments from Lua files recursively using parallel processing.
Supports multiple input directories and provides prettier-style output.
"""

import sys
import re
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Tuple, Optional
from dataclasses import dataclass
from itertools import chain


@dataclass
class FileStats:
    """Statistics for a processed Lua file."""

    path: Path
    original_size: int
    new_size: int
    lines_removed: int
    comments_removed: int

    @property
    def size_reduction(self) -> float:
        """Calculate size reduction as percentage."""
        if self.original_size > 0:
            return (1 - self.new_size / self.original_size) * 100
        return 0.0

    @property
    def relpath(self) -> Path:
        """Get relative path from current directory."""
        try:
            return self.path.relative_to(Path.cwd())
        except ValueError:
            return self.path


def strip_lua_comments(content: str) -> Tuple[str, int, int]:
    """
    Remove comments from Lua code.
    Returns (stripped_content, lines_removed, comments_removed).
    """
    lines = content.splitlines(keepends=True)
    result_lines = []
    lines_removed = 0
    comments_removed = 0
    in_multiline_comment = False

    for line in lines:
        # Check if we're in a multiline comment
        if in_multiline_comment:
            comments_removed += 1
            if "]]" in line or "--[[" in line:
                end_idx = line.find("]]")
                if end_idx != -1:
                    # Check if there's anything after the comment end
                    remaining = line[end_idx + 2 :]
                    # Also check for nested comments
                    if "--[[" in line[:end_idx]:
                        # Nested comment continues
                        pass
                    else:
                        in_multiline_comment = False
                        if remaining.strip():
                            # There's code after the comment
                            # Add a blank line to preserve line numbers if needed
                            result_lines.append("\n")
                            lines_removed -= 1  # Compensate for adding blank line
                        else:
                            lines_removed += 1
                            continue
                else:
                    lines_removed += 1
                    continue
            else:
                lines_removed += 1
                continue

        # Handle single-line and multiline comments
        stripped_line = line
        had_comment = False

        # Check for multiline comment start
        if "--[[" in line:
            start_idx = line.find("--[[")
            before_comment = line[:start_idx]

            # Check if the comment ends on the same line
            end_idx = line.find("]]", start_idx + 4)
            if end_idx != -1:
                # Comment starts and ends on same line
                after_comment = line[end_idx + 2 :]
                stripped_line = before_comment + after_comment
                if not stripped_line.strip():
                    if before_comment.strip():
                        stripped_line = before_comment.rstrip() + "\n"
                    else:
                        lines_removed += 1
                        comments_removed += 1
                        continue
                had_comment = True
                comments_removed += 1
            else:
                # Comment continues to next line
                if before_comment.strip():
                    stripped_line = before_comment.rstrip() + "\n"
                else:
                    in_multiline_comment = True
                    lines_removed += 1
                    comments_removed += 1
                    continue
                had_comment = True
                comments_removed += 1

        # Handle single-line comments (not part of multiline)
        if not in_multiline_comment and "--" in line and "--[[" not in line:
            # Find all occurrences of -- that are not inside strings
            in_string = False
            string_char = None
            comment_start = -1

            for i in range(len(line) - 1):
                if line[i] in ('"', "'") and (i == 0 or line[i - 1] != "\\"):
                    if not in_string:
                        in_string = True
                        string_char = line[i]
                    elif line[i] == string_char:
                        in_string = False
                elif not in_string and line[i : i + 2] == "--":
                    comment_start = i
                    break

            if comment_start != -1:
                stripped_line = line[:comment_start]
                had_comment = True
                comments_removed += 1
                if not stripped_line.strip():
                    lines_removed += 1
                    continue
                stripped_line = stripped_line.rstrip() + "\n"

        result_lines.append(stripped_line)

    stripped_content = "".join(result_lines)
    return stripped_content, lines_removed, comments_removed


def process_lua_file(file_path: Path) -> Optional[FileStats]:
    """
    Process a single Lua file to remove comments.
    Returns FileStats if successful, None otherwise.
    """
    try:
        # Read the original file
        original_content = file_path.read_text(encoding="utf-8")
        original_size = len(original_content.encode("utf-8"))

        # Strip comments
        stripped_content, lines_removed, comments_removed = strip_lua_comments(original_content)

        # Write back only if changed
        if stripped_content != original_content:
            file_path.write_text(stripped_content, encoding="utf-8")
            new_size = len(stripped_content.encode("utf-8"))
        else:
            new_size = original_size

        return FileStats(
            path=file_path,
            original_size=original_size,
            new_size=new_size,
            lines_removed=lines_removed,
            comments_removed=comments_removed,
        )

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return None


def find_lua_files(directories: list[Path]) -> list[Path]:
    """Find all .lua files recursively in the given directories."""
    lua_files = []
    for directory in directories:
        if directory.is_dir():
            lua_files.extend(directory.rglob("*.lua"))
        elif directory.suffix == ".lua":
            lua_files.append(directory)
    return sorted(set(lua_files))  # Remove duplicates and sort


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    for unit in ["B", "kB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def main():
    """Main entry point."""
    # Parse directories from command line arguments
    if len(sys.argv) > 1:
        directories = [Path(d).resolve() for d in sys.argv[1:]]
    else:
        directories = [Path.cwd()]

    print(f"\n🔍 Searching for Lua files in:")
    for directory in directories:
        print(f"   {directory}")

    # Find all Lua files
    lua_files = find_lua_files(directories)

    if not lua_files:
        print("\n✨ No Lua files found.")
        return

    print(f"\n📝 Found {len(lua_files)} Lua file(s)")
    print("=" * 70)

    # Process files in parallel
    stats_list = []
    processed = 0
    errors = 0

    with ProcessPoolExecutor() as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_lua_file, file_path): file_path for file_path in lua_files}

        # Process completed tasks
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                stats = future.result()
                if stats:
                    stats_list.append(stats)
                    processed += 1

                    # Print per-file stats
                    status = "modified" if stats.original_size != stats.new_size else "unchanged"
                    reduction = f"-{stats.size_reduction:.1f}%" if stats.size_reduction > 0 else "0%"

                    print(f"  {status:9} {reduction:>8}  {stats.relpath}")

                    if stats.comments_removed > 0:
                        print(f"           {'':9} {'':>8}  ↳ {stats.comments_removed} comment(s) removed")
                else:
                    errors += 1
            except Exception as e:
                print(f"  error     {'':>8}  {file_path.relative_to(Path.cwd())}")
                print(f"           {'':9} {'':>8}  ↳ {e}")
                errors += 1

    # Print summary
    print("=" * 70)

    total_original = sum(s.original_size for s in stats_list)
    total_new = sum(s.new_size for s in stats_list)
    total_saved = total_original - total_new
    total_reduction = (1 - total_new / total_original) * 100 if total_original > 0 else 0
    total_comments = sum(s.comments_removed for s in stats_list)
    total_lines = sum(s.lines_removed for s in stats_list)
    modified_files = sum(1 for s in stats_list if s.original_size != s.new_size)

    print(f"\n📊 Summary:")
    print(f"   Files processed:  {processed} ({modified_files} modified, {processed - modified_files} unchanged)")
    if errors:
        print(f"   Errors:           {errors}")
    print(f"   Comments removed: {total_comments}")
    print(f"   Lines removed:    {total_lines}")
    print(f"   Size reduction:   {format_size(total_saved)} ({total_reduction:.1f}%)")
    print(f"   Total size:       {format_size(total_original)} → {format_size(total_new)}")

    if errors:
        print(f"\n⚠️  Completed with {errors} error(s)")
        sys.exit(1)
    else:
        print(f"\n✅ Done in {processed} file(s)\n")


if __name__ == "__main__":
    main()
