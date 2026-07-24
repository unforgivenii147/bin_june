#!/data/data/com.termux/files/home/.local/bin/python
"""Recursively replace or remove text in files with Python 3.12+ optimizations."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Constants
SKIP_DIRS = frozenset(
    {".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "node_modules", "build", "dist"}
)
CHUNK_SIZE = 8192  # Was undefined
MAX_CONTEXT_DISPLAY = 3  # Magic number extracted


def is_binary(path: Path) -> bool:
    """Check if a file is binary by sampling its content."""
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)

        if not chunk:
            return False

        # Check for null bytes (strong indicator of binary)
        if b"\x00" in chunk:
            return True

        # Check ratio of non-text characters
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\b"
        nontext = sum(1 for byte in chunk if byte not in text_chars)
        return (nontext / len(chunk)) > 0.3

    except (OSError, PermissionError):
        return True  # Treat unreadable files as binary


def process_file(path: Path, search_text: str, replace_text: str | None = None, dry_run: bool = False) -> bool:
    """Process a single file for text replacement.

    Returns True if matches were found, False otherwise.
    """
    try:
        content = path.read_text(encoding="utf-8")

        # Use compiled pattern for efficiency
        pattern = re.compile(re.escape(search_text))

        if not pattern.search(content):
            return False

        replacement = "" if replace_text is None else replace_text

        if dry_run:
            matches = list(pattern.finditer(content))
            print(f"[DRY RUN] Found {len(matches)} match(es) in {path}")

            # Show context for first few matches
            for i, match in enumerate(matches[:MAX_CONTEXT_DISPLAY]):
                start = max(0, match.start() - 20)
                end = min(len(content), match.end() + 20)
                context = content[start:end].replace("\n", " ").strip()
                print(f"  Match {i + 1}: ...{context}...")

            if len(matches) > MAX_CONTEXT_DISPLAY:
                print(f"  ... and {len(matches) - MAX_CONTEXT_DISPLAY} more matches")
        else:
            new_content = pattern.sub(replacement, content)
            path.write_text(new_content, encoding="utf-8")
            print(f"Updated: {path}")

        return True

    except (UnicodeDecodeError, PermissionError) as e:
        print(f"Skipping {path}: {e}", file=sys.stderr)
        return False
    except IsADirectoryError:
        return False
    except OSError as e:
        print(f"Error processing {path}: {e}", file=sys.stderr)
        return False


def replace_in_files(
    search_text: str, replace_text: str | None = None, target_file: str | None = None, dry_run: bool = False
) -> tuple[int, int]:
    """Recursively process files for text replacement.

    Returns tuple of (files_processed, files_changed).
    """
    files_processed = 0
    files_changed = 0

    # Single file mode
    if target_file:
        path = Path(target_file)
        if not path.is_file() or path.is_symlink():
            print(f"Error: {target_file} is not a valid file", file=sys.stderr)
            return 0, 0

        print(f"Processing file: {target_file}")
        if process_file(path, search_text, replace_text, dry_run):
            files_changed += 1
        return 1, files_changed

    # Recursive directory mode
    for root, dirs, files in os.walk("."):
        # Filter directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for filename in files:
            path = Path(root) / filename

            # Skip symlinks and binary files
            if path.is_symlink() or is_binary(path):
                continue

            files_processed += 1

            if process_file(path, search_text, replace_text, dry_run):
                files_changed += 1

            # Progress indicator every 100 files
            if files_processed % 100 == 0:
                print(f"Processed {files_processed} files...", end="\r")

    return files_processed, files_changed


def parse_search_replace(strings: list[str]) -> tuple[str, str | None]:
    """Parse search and optional replacement strings from arguments."""
    if len(strings) == 2:
        search_text, replace_text = strings
        action = f"REPLACING '{search_text}' WITH '{replace_text}'"
    elif len(strings) == 1:
        search_text = strings[0]
        replace_text = None
        action = f"REMOVING '{search_text}'"
    else:
        raise ValueError("Expected 1 or 2 strings")

    # Strip quotes if present
    if search_text.startswith(("'", '"')) and search_text.endswith(("'", '"')):
        search_text = search_text[1:-1]

    return search_text, replace_text, action


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Recursively replace or remove text in files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        "  %(prog)s 'old_text' 'new_text'  # Replace text\n"
        "  %(prog)s 'text_to_remove'      # Remove text\n"
        "  %(prog)s 'text' --dry-run      # Preview changes",
    )
    parser.add_argument(
        "strings",
        nargs="+",
        help="Search text and optional replacement text. If only one string is provided, it will be removed.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying them")
    parser.add_argument("-f", "--file", help="Process only the specified file instead of recursive directory search")

    args = parser.parse_args()

    # Parse search/replace strings
    try:
        search_text, replace_text, action = parse_search_replace(args.strings)
    except ValueError:
        parser.error("Please provide either one string (to remove) or two strings (search and replace)")
        return

    # Display mode information
    if args.dry_run:
        print("--- RUNNING IN DRY RUN MODE (No files will be modified) ---")
    print(f"--- {action} ---")

    # Process files
    files_processed, files_changed = replace_in_files(
        search_text, replace_text, target_file=args.file, dry_run=args.dry_run
    )

    # Summary
    print(f"\n--- Complete: Processed {files_processed} files, modified {files_changed} files ---")


if __name__ == "__main__":
    main()
