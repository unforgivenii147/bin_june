#!/data/data/com.termux/files/usr/bin/env python
"""
Remove duplicate entries from $PATH and update ~/.bashrc
"""

import os
import sys
from pathlib import Path


def get_path_entries():
    """Get current PATH entries from environment."""
    path_str = os.environ.get("PATH", "")
    return path_str.split(":") if path_str else []


def remove_duplicates_preserve_order(entries):
    """Remove duplicates while preserving the original order."""
    seen = set()
    unique_entries = []
    for entry in entries:
        if entry and entry not in seen:  # Skip empty strings
            seen.add(entry)
            print(entry)
            unique_entries.append(entry)
    return unique_entries


def read_bashrc(bashrc_path):
    """Read the current .bashrc file."""
    if bashrc_path.exists():
        return bashrc_path.read_text()
    return ""


def update_bashrc_with_path(bashrc_content, new_path_entries):
    """Update or add the PATH export line in bashrc content."""
    new_path_str = ":".join(new_path_entries)
    path_export = f'export PATH="{new_path_str}"\n'

    # Check if PATH is already defined in bashrc
    lines = bashrc_content.split("\n")
    path_line_indices = [i for i, line in enumerate(lines) if line.strip().startswith("export PATH=")]

    if path_line_indices:
        # Replace the first occurrence
        lines[path_line_indices[0]] = path_export.rstrip()
        updated_content = "\n".join(lines)
    else:
        # Append to the end
        updated_content = bashrc_content.rstrip() + "\n" + path_export

    return updated_content


def main():
    """Main function."""
    bashrc_path = Path.home() / ".bashrc"

    # Get current PATH entries
    path_entries = get_path_entries()
    print(f"Current PATH entries: {len(path_entries)}")

    # Remove duplicates
    unique_entries = remove_duplicates_preserve_order(path_entries)
    print(f"Unique PATH entries: {len(unique_entries)}")
    print(f"Removed {len(path_entries) - len(unique_entries)} duplicate(s)")

    if len(path_entries) == len(unique_entries):
        print("✓ No duplicates found!")
        return

    # Show what was removed
    print("\nDuplicate entries removed:")
    for entry in path_entries:
        if entry not in unique_entries:
            print(f"  - {entry}")

    # Read current bashrc
    bashrc_content = read_bashrc(bashrc_path)

    # Update bashrc with deduplicated PATH
    updated_content = update_bashrc_with_path(bashrc_content, unique_entries)

    # Backup original bashrc
    backup_path = bashrc_path.with_suffix(".bashrc.backup")
    if bashrc_path.exists():
        bashrc_path.write_text(bashrc_content)
        backup_path.write_text(bashrc_content)
        print(f"\n✓ Backed up original to {backup_path}")

    # Write updated bashrc
    bashrc_path.write_text(updated_content)
    print(f"✓ Updated {bashrc_path}")
    print("\nNote: Run 'source ~/.bashrc' to apply changes to current shell")


if __name__ == "__main__":
    main()
