#!/data/data/com.termux/files/usr/bin/python
"""
Check for bash functions that also exist as aliases and remove the aliases.
"""

import os
import re
import sys
from pathlib import Path


def extract_function_names(filepath: Path):
    """Extract function names from a bash functions file."""
    functions = set()
    function_pattern = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*\(\s*\)\s*\{", re.MULTILINE)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            matches = function_pattern.findall(content)
            functions.update(matches)
    except FileNotFoundError:
        print(f"Error: Functions file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading functions file: {e}")
        sys.exit(1)

    return functions


def extract_alias_names(filepath: Path):
    """Extract alias names from a bash aliases file."""
    aliases = {}
    alias_pattern = re.compile(r"^\s*alias\s+([a-zA-Z_][a-zA-Z0-9_-]*)=", re.MULTILINE)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_line = ""
        for line in lines:
            current_line += line
            if "\\\n" in line:
                continue  # Line continues
            # Process complete line
            matches = alias_pattern.findall(current_line)
            for match in matches:
                aliases[match] = current_line
            current_line = ""

    except FileNotFoundError:
        print(f"Error: Aliases file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading aliases file: {e}")
        sys.exit(1)

    return aliases


def remove_aliases(aliases_to_remove, aliases_file: Path) -> int:
    """Remove specific aliases from the aliases file."""
    if not aliases_to_remove:
        return 0

    try:
        with open(aliases_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Filter out lines containing the aliases to remove
        new_lines = []
        removed_count = 0
        skip_next = False

        for i, line in enumerate(lines):
            if skip_next:
                skip_next = False
                continue

            # Check if this line contains an alias to remove
            removed = False
            for alias in aliases_to_remove:
                if re.match(rf"^\s*alias\s+{alias}=", line):
                    removed = True
                    removed_count += 1
                    print(f"Removing alias: {alias}")
                    # Check if line ends with backslash (continuation)
                    if line.rstrip().endswith("\\"):
                        skip_next = True
                    break

            if not removed:
                new_lines.append(line)

        # Write back the file
        if removed_count > 0:
            with open(aliases_file, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"\nRemoved {removed_count} alias(es) from {aliases_file}")
        else:
            print("No aliases were removed")

        return removed_count

    except Exception as e:
        print(f"Error modifying aliases file: {e}")
        return 0


def create_backup(filepath: Path) -> str | None:
    """Create a backup of the aliases file."""
    if not os.path.exists(filepath):
        return None

    backup_path = f"{filepath}.backup"
    try:
        import shutil

        shutil.copy2(filepath, backup_path)
        print(f"Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"Warning: Could not create backup: {e}")
        return None


def main() -> None:
    # Define file paths
    bashd = Path.home() / ".config/bash.d"
    functions_file = bashd / "bash_functions"
    aliases_file = bashd / "bash_aliases"

    functions = extract_function_names(functions_file)
    aliases = extract_alias_names(aliases_file)

    if not functions:
        print("No functions found in functions file")
        sys.exit(0)

    if not aliases:
        print("No aliases found in aliases file")
        sys.exit(0)

    print(f"Found {len(functions)} function(s)")
    print(f"Found {len(aliases)} alias(es)")
    print("-" * 50)

    # Find conflicting aliases
    conflicts = functions.intersection(aliases.keys())

    if not conflicts:
        print("No conflicts found - no aliases match function names")
        sys.exit(0)

    print(f"Found {len(conflicts)} conflicting alias(es):")
    for conflict in sorted(conflicts):
        print(f"  - {conflict} (alias: {aliases[conflict].strip()})")

    print("-" * 50)

    # Ask for confirmation
    response = input(f"\nRemove these {len(conflicts)} conflicting aliases? [y/N]: ").strip().lower()

    if response != "y":
        print("Operation cancelled")
        sys.exit(0)

    # Create backup before modifying
    backup = create_backup(aliases_file)

    # Remove aliases
    removed = remove_aliases(conflicts, aliases_file)

    if removed > 0:
        print(f"\n✓ Successfully removed {removed} alias(es)")
        if backup:
            print(f"Backup saved at: {backup}")
        print("\nPlease reload your bash configuration:")
        print("source ~/.bashrc")
        print("  # or")
        print("  exec $SHELL")
    else:
        print("\nNo aliases were removed")
        sys.exit(1)


if __name__ == "__main__":
    main()
