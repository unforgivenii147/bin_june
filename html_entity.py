#!/usr/bin/env python3
"""
Convert HTML entities in HTML files recursively.
Converts &lt; to <, &gt; to >, and other common entities.
"""

import multiprocessing as mp
from pathlib import Path
import re
from functools import partial

# HTML entity mappings
HTML_ENTITIES = {
    "&lt;": "<",
    "&gt;": ">",
    "&amp;": "&",
    "&quot;": '"',
    "&apos;": "'",
    "&nbsp;": " ",
    "&copy;": "©",
    "&reg;": "®",
    "&euro;": "€",
    "&pound;": "£",
    "&yen;": "¥",
    "&dollar;": "$",
    "&cent;": "¢",
    "&sect;": "§",
    "&dagger;": "†",
    "&Dagger;": "‡",
    "&hellip;": "…",
    "&mdash;": "—",
    "&ndash;": "–",
    "&lsquo;": "'",
    "&rsquo;": "'",
    "&ldquo;": '"',
    "&rdquo;": '"',
}

# Create regex pattern for efficient replacement
# Order matters: &amp; must be processed before entities that contain '&'
# So we'll process it separately or ensure proper ordering
ENTITY_PATTERN = re.compile("|".join(re.escape(k) for k in HTML_ENTITIES.keys()))


def replace_entities(text: str) -> str:
    """Replace HTML entities with their characters."""

    def replacer(match):
        return HTML_ENTITIES[match.group(0)]

    return ENTITY_PATTERN.sub(replacer, text)


def process_file(filepath: Path, dry_run: bool = False) -> tuple[Path, bool, str]:
    """
    Process a single HTML file, converting entities in-place.
    Returns (filepath, changed, error_message)
    """
    try:
        # Read file content
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Replace entities
        new_content = replace_entities(content)

        # Check if changes were made
        changed = content != new_content

        if changed and not dry_run:
            # Write back if changes exist
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)

        return (filepath, changed, "")

    except Exception as e:
        return (filepath, False, str(e))


def find_html_files(directory: Path, extensions: list = None) -> list[Path]:
    """Recursively find all HTML files."""
    if extensions is None:
        extensions = [".html", ".htm", ".xhtml"]

    html_files = []
    for ext in extensions:
        html_files.extend(directory.rglob(f"*{ext}"))

    return html_files


def main(directory: str = ".", dry_run: bool = False, num_workers: int = None):
    """
    Main function to convert HTML entities in all HTML files.

    Args:
        directory: Root directory to search for HTML files
        dry_run: If True, only show what would be changed without modifying files
        num_workers: Number of worker processes (default: CPU count)
    """
    root_dir = Path(directory)

    if not root_dir.exists():
        print(f"Error: Directory '{directory}' does not exist")
        return

    if not root_dir.is_dir():
        print(f"Error: '{directory}' is not a directory")
        return

    # Find all HTML files
    print(f"Searching for HTML files in {root_dir.absolute()}...")
    html_files = find_html_files(root_dir)

    if not html_files:
        print("No HTML files found.")
        return

    print(f"Found {len(html_files)} HTML files to process")

    if dry_run:
        print("DRY RUN MODE - No files will be modified")

    # Determine number of workers
    if num_workers is None:
        num_workers = mp.cpu_count()

    print(f"Using {num_workers} worker processes")

    # Process files in parallel
    process_func = partial(process_file, dry_run=dry_run)

    changed_files = []
    error_files = []

    with mp.Pool(processes=num_workers) as pool:
        results = pool.map(process_func, html_files)

        for filepath, changed, error in results:
            if error:
                error_files.append((filepath, error))
            elif changed:
                changed_files.append(filepath)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if changed_files:
        print(f"\n✅ Modified {len(changed_files)} file(s):")
        for f in changed_files:
            print(f"  - {f.relative_to(root_dir)}")
    else:
        print("\n✅ No files were modified")

    if error_files:
        print(f"\n❌ Errors in {len(error_files)} file(s):")
        for f, err in error_files:
            print(f"  - {f.relative_to(root_dir)}: {err}")

    print(f"\n📊 Total files processed: {len(html_files)}")
    print(f"   Modified: {len(changed_files)}")
    print(f"   Errors: {len(error_files)}")

    if dry_run and changed_files:
        print("\n💡 To actually modify files, run without --dry-run flag")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert HTML entities (like &lt;, &gt;) in HTML files recursively")
    parser.add_argument(
        "directory", nargs="?", default=".", help="Root directory to search for HTML files (default: current directory)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes (default: CPU count)")

    args = parser.parse_args()

    main(args.directory, args.dry_run, args.workers)
