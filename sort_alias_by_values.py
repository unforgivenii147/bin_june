#!/data/data/com.termux/files/usr/bin/python
"""
Sort bash aliases by their value (the part after =).
"""

import re
import sys
from pathlib import Path


def parse_aliases(filepath):
    """Parse aliases file and return list of (name, value, raw_line) tuples."""
    aliases = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Handle line continuations (backslash at end of line)
        content = re.sub(r"\\\n", "", content)

        # Find all alias definitions
        # Pattern matches: alias name=value (value can be quoted or unquoted)
        pattern = re.compile(r"^\s*alias\s+([a-zA-Z_][a-zA-Z0-9_-]*)\s*=\s*(.+?)\s*$", re.MULTILINE)

        for match in pattern.finditer(content):
            name = match.group(1)
            value = match.group(2).strip()

            # Remove surrounding quotes if present
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            aliases.append((name, value, match.group(0)))

    except FileNotFoundError:
        print(f"Error: Aliases file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    return aliases


def write_sorted_aliases(aliases, filepath, create_backup=True):
    """Write sorted aliases back to file."""

    # Sort by value (the second element in the tuple)
    sorted_aliases = sorted(aliases, key=lambda x: x[1])

    # Create backup if requested
    if create_backup:
        backup_path = f"{filepath}.backup"
        try:
            from shutil import copy2

            copy2(filepath, backup_path)
            print(f"Backup created: {backup_path}")
        except Exception as e:
            print(f"Warning: Could not create backup: {e}")

    # Write sorted aliases
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            for name, value, raw_line in sorted_aliases:
                # Preserve original formatting if possible
                f.write(raw_line + "\n")

        print(f"\n✓ Sorted {len(sorted_aliases)} aliases by value")
        print(f"Output written to: {filepath}")

    except Exception as e:
        print(f"Error writing file: {e}")
        sys.exit(1)


def display_aliases(aliases, limit=None):
    """Display aliases in a formatted table."""
    if not aliases:
        print("No aliases found")
        return

    # Sort for display
    sorted_aliases = sorted(aliases, key=lambda x: x[1])

    if limit:
        sorted_aliases = sorted_aliases[:limit]

    # Find max lengths for formatting
    max_name_len = max(len(name) for name, _, _ in sorted_aliases)
    max_value_len = max(len(value) for _, value, _ in sorted_aliases)
    max_value_len = min(max_value_len, 60)  # Cap at 60 chars

    print(f"\n{'ALIAS':<{max_name_len}}  {'VALUE':<{max_value_len}}")
    print("-" * (max_name_len + max_value_len + 2))

    for name, value, _ in sorted_aliases:
        # Truncate long values
        if len(value) > 60:
            value = value[:57] + "..."
        print(f"{name:<{max_name_len}}  {value:<{max_value_len}}")


def main():
    # Get the aliases file path
    aliases_file = Path.home() / ".config/bash.d/bash_aliases"

    # Allow command line argument for custom path
    if len(sys.argv) > 1:
        aliases_file = Path(sys.argv[1])

    print(f"Reading aliases from: {aliases_file}")
    print("-" * 50)

    # Parse aliases
    aliases = parse_aliases(aliases_file)

    if not aliases:
        print("No aliases found in file")
        sys.exit(0)

    print(f"Found {len(aliases)} alias(es)")

    # Show preview before sorting
    print("\n--- BEFORE SORTING (first 10 by value) ---")
    display_aliases(aliases, limit=10)

    # Ask for confirmation
    print("\n" + "-" * 50)
    response = input(f"Sort all {len(aliases)} aliases by value? [y/N]: ").strip().lower()

    if response != "y":
        print("Operation cancelled")
        sys.exit(0)

    # Write sorted aliases
    write_sorted_aliases(aliases, aliases_file, create_backup=True)

    # Show preview after sorting
    print("\n--- AFTER SORTING (first 10 by value) ---")
    sorted_preview = sorted(aliases, key=lambda x: x[1])[:10]
    display_aliases(sorted_preview)

    print("\n✓ Done! Reload your shell to use the sorted aliases:")
    print("  source ~/.bashrc")
    print("  # or")
    print("  exec $SHELL")


if __name__ == "__main__":
    main()
