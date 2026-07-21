#!/data/data/com.termux/files/usr/bin/env python
"""
Remove image references (including shields.io badges) from .rst and .md files.
Processes files in parallel and reports statistics.
"""

import re
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FileStats:
    """Statistics for processed files."""

    path: Path
    lines_before: int
    lines_after: int
    size_before: int
    size_after: int
    removed_lines: int
    removed_refs: int


# Patterns for image references in RST files
RST_IMAGE_PATTERNS = [
    # .. image:: https://img.shields.io/...
    re.compile(r"^\s*\.\.\s+image::\s+https?://[^\s]+", re.IGNORECASE | re.MULTILINE),
    # .. figure:: https://...
    re.compile(r"^\s*\.\.\s+figure::\s+https?://[^\s]+", re.IGNORECASE | re.MULTILINE),
    # |badge| image:: https://...
    re.compile(r"^\s*\.\.\s+\|.*\|\s+image::\s+https?://[^\s]+", re.IGNORECASE | re.MULTILINE),
    # .. image:: /path/to/image.png (local images too)
    re.compile(r"^\s*\.\.\s+image::\s+(?!https?://)[^\s]+", re.IGNORECASE | re.MULTILINE),
    # .. figure:: /path/to/image.png (local images too)
    re.compile(r"^\s*\.\.\s+figure::\s+(?!https?://)[^\s]+", re.IGNORECASE | re.MULTILINE),
    # Substitution definitions with URLs
    re.compile(
        r"^\s*\.\.\s+\|.*\|\s+replace::\s+https?://[^\s]+\.(?:png|jpg|jpeg|gif|svg|ico)(?:\?[^\s]*)?",
        re.IGNORECASE | re.MULTILINE,
    ),
]

# Patterns for image references in Markdown files
MD_IMAGE_PATTERNS = [
    # ![alt](https://img.shields.io/...)
    re.compile(r"!\[.*?\]\(https?://[^\)]+\)", re.IGNORECASE),
    # ![alt](image.png)
    re.compile(r"!\[.*?\]\((?!https?://)[^\)]+\)", re.IGNORECASE),
    # <img src="...">
    re.compile(r'<img[^>]+src\s*=\s*["\'][^"\']+["\'][^>]*>', re.IGNORECASE),
    # HTML img tags with shields.io or other image URLs
    re.compile(r"<img[^>]*>", re.IGNORECASE),
    # Reference style images: [img]: https://img.shields.io/...
    re.compile(r"^\[.*?\]:\s+https?://[^\s]+\.(?:png|jpg|jpeg|gif|svg|ico)(?:\?[^\s]*)?", re.IGNORECASE | re.MULTILINE),
    # Inline HTML for badges
    re.compile(r'<a\s+href="[^"]*">\s*<img[^>]*>\s*</a>', re.IGNORECASE),
]


def is_image_url(line: str) -> bool:
    """Check if a line contains an image URL reference."""
    image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp")
    image_domains = (
        "shields.io",
        "badge.fury.io",
        "travis-ci.org",
        "travis-ci.com",
        "circleci.com",
        "codecov.io",
        "coveralls.io",
        "img.shields.io",
    )

    # Check for image URLs
    for domain in image_domains:
        if domain in line:
            return True

    # Check for common image extensions in URLs
    for ext in image_extensions:
        if ext in line.lower():
            return True

    return False


def remove_image_lines_rst(content: str) -> Tuple[str, int]:
    """Remove image references from RST content."""
    lines = content.split("\n")
    new_lines = []
    removed_count = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        should_remove = False

        # Check if this line matches any RST image pattern
        for pattern in RST_IMAGE_PATTERNS:
            if pattern.match(line):
                should_remove = True
                break

        # Check for inline image URLs
        if not should_remove and is_image_url(line):
            if "image::" in line or "figure::" in line or "replace::" in line:
                should_remove = True

        if should_remove:
            removed_count += 1
            # Also skip the next line if it's an option line (starting with :)
            if i + 1 < len(lines) and lines[i + 1].strip().startswith(":"):
                i += 1
        else:
            new_lines.append(line)

        i += 1

    return "\n".join(new_lines), removed_count


def remove_image_lines_md(content: str) -> Tuple[str, int]:
    """Remove image references from Markdown content."""
    lines = content.split("\n")
    new_lines = []
    removed_count = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        original_line = line
        should_remove = False

        # Check for Markdown image patterns
        for pattern in MD_IMAGE_PATTERNS:
            if pattern.search(line):
                # Try to remove just the image part
                new_line = pattern.sub("", line).strip()
                if new_line:
                    # If there's remaining content, keep it
                    line = new_line
                else:
                    # If line becomes empty after removal, mark for deletion
                    if pattern.search(original_line):
                        should_remove = True
                        break

        # Check for inline image URLs not caught by patterns
        if not should_remove and is_image_url(line):
            if "![" in line and "](" in line:
                should_remove = True
            elif "<img" in line.lower():
                should_remove = True

        if should_remove:
            removed_count += 1
        else:
            if line.strip():  # Only add non-empty lines
                new_lines.append(line)
            else:
                new_lines.append(line)  # Keep empty lines for structure

        i += 1

    # Clean up multiple consecutive empty lines
    cleaned_lines = []
    prev_empty = False
    for line in new_lines:
        is_empty = not line.strip()
        if is_empty and prev_empty:
            continue
        cleaned_lines.append(line)
        prev_empty = is_empty

    return "\n".join(cleaned_lines), removed_count


def process_file(file_path: Path) -> Optional[FileStats]:
    """Process a single file and return statistics."""
    try:
        # Read file
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines_before = content.count("\n") + 1
        size_before = len(content.encode("utf-8"))

        # Process based on file extension
        suffix = file_path.suffix.lower()
        if suffix == ".rst":
            new_content, removed_refs = remove_image_lines_rst(content)
        elif suffix == ".md":
            new_content, removed_refs = remove_image_lines_md(content)
        else:
            return None

        # Only write if changes were made
        if removed_refs > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            lines_after = new_content.count("\n") + 1
            size_after = len(new_content.encode("utf-8"))

            return FileStats(
                path=file_path,
                lines_before=lines_before,
                lines_after=lines_after,
                size_before=size_before,
                size_after=size_after,
                removed_lines=lines_before - lines_after,
                removed_refs=removed_refs,
            )

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return None


def collect_files(directories: List[Path]) -> List[Path]:
    """Collect all .rst and .md files from given directories."""
    files = []
    for directory in directories:
        if not directory.exists():
            print(f"Warning: Directory '{directory}' does not exist, skipping...", file=sys.stderr)
            continue
        if not directory.is_dir():
            print(f"Warning: '{directory}' is not a directory, skipping...", file=sys.stderr)
            continue

        # Collect .rst and .md files
        for ext in ["*.rst", "*.md"]:
            files.extend(directory.rglob(ext))

    return sorted(set(files))  # Remove duplicates and sort


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def print_stats(all_stats: List[FileStats], base_path: Path):
    """Print formatted statistics."""
    if not all_stats:
        print("\n✨ No image references found to remove!")
        return

    print("\n" + "=" * 80)
    print("📊 IMAGE REFERENCE REMOVAL REPORT")
    print("=" * 80)

    total_lines_before = 0
    total_lines_after = 0
    total_size_before = 0
    total_size_after = 0
    total_removed_refs = 0

    for stats in all_stats:
        rel_path = stats.path.relative_to(base_path)
        size_change = stats.size_before - stats.size_after
        change_symbol = "↓" if size_change > 0 else "→"

        print(f"\n📄 {rel_path}")
        print(f"   ├─ Image references removed: {stats.removed_refs}")
        print(f"   ├─ Lines: {stats.lines_before} → {stats.lines_after} ({stats.removed_lines:+d})")
        print(
            f"   ├─ Size: {format_size(stats.size_before)} → {format_size(stats.size_after)} "
            f"({change_symbol} {format_size(abs(size_change))})"
        )
        print(f"   └─ Reduction: {(size_change / stats.size_before * 100):.1f}%")

        total_lines_before += stats.lines_before
        total_lines_after += stats.lines_after
        total_size_before += stats.size_before
        total_size_after += stats.size_after
        total_removed_refs += stats.removed_refs

    print("\n" + "=" * 80)
    print("📈 SUMMARY")
    print("=" * 80)
    print(f"Files modified: {len(all_stats)}")
    print(f"Total image references removed: {total_removed_refs}")
    print(f"Total lines: {total_lines_before} → {total_lines_after} ({total_lines_before - total_lines_after:+d})")
    print(
        f"Total size: {format_size(total_size_before)} → {format_size(total_size_after)} "
        f"({format_size(total_size_before - total_size_after)} saved)"
    )
    if total_size_before > 0:
        print(f"Overall reduction: {((total_size_before - total_size_after) / total_size_before * 100):.1f}%")
    print("=" * 80 + "\n")


def main():
    """Main function to process files."""
    # Parse command line arguments
    if len(sys.argv) > 1:
        directories = [Path(arg) for arg in sys.argv[1:]]
    else:
        directories = [Path.cwd()]

    print("🔍 Scanning for .rst and .md files...")

    # Collect files
    files = collect_files(directories)
    print(f"Found {len(files)} files to process")

    if not files:
        print("No .rst or .md files found in the specified directories.")
        return

    # Process files in parallel
    print("⚡ Processing files in parallel...")
    stats_list = []

    with ProcessPoolExecutor() as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_file, file): file for file in files}

        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_file):
            completed += 1
            file = future_to_file[future]

            try:
                stats = future.result()
                if stats:
                    stats_list.append(stats)

                # Progress indicator
                if completed % 10 == 0 or completed == len(files):
                    print(f"  Progress: {completed}/{len(files)} files processed", end="\r")

            except Exception as e:
                print(f"\nError processing {file}: {e}", file=sys.stderr)

    print(f"\n✅ Processed {len(files)} files")

    # Print statistics
    base_path = Path.cwd()
    print_stats(stats_list, base_path)


if __name__ == "__main__":
    main()
