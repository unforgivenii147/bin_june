#!/data/data/com.termux/files/usr/bin/env python


"""
Sort bash aliases by their value (the part after =).
"""

import re
import sys
from pathlib import Path


def parse_aliases(filepath: Path):
    aliases = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r"\\\n", "", content)
        pattern = re.compile("^\\s*alias\\s+([a-zA-Z_][a-zA-Z0-9_-]*)\\s*=\\s*(.+?)\\s*$", re.MULTILINE)
        for match in pattern.finditer(content):
            name = match.group(1)
            value = match.group(2).strip()
            if value.startswith('"') and value.endswith('"') or value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            aliases.append((name, value, match.group(0)))
    except FileNotFoundError:
        print(f"Error: Aliases file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    return aliases


def write_sorted_aliases(aliases, filepath: Path, create_backup=True) -> None:
    sorted_aliases = sorted(aliases, key=lambda x: x[1])
    if create_backup:
        backup_path = f"{filepath}.backup"
        try:
            from shutil import copy2

            copy2(filepath, backup_path)
            print(f"Backup created: {backup_path}")
        except Exception as e:
            print(f"Warning: Could not create backup: {e}")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            for name, value, raw_line in sorted_aliases:
                f.write(raw_line + "\n")
        print(f"\n✓ Sorted {len(sorted_aliases)} aliases by value")
        print(f"Output written to: {filepath}")
    except Exception as e:
        print(f"Error writing file: {e}")
        sys.exit(1)


def display_aliases(aliases, limit=None) -> None:
    if not aliases:
        print("No aliases found")
        return
    sorted_aliases = sorted(aliases, key=lambda x: x[1])
    if limit:
        sorted_aliases = sorted_aliases[:limit]
    max_name_len = max(len(name) for name, _, _ in sorted_aliases)
    max_value_len = max(len(value) for _, value, _ in sorted_aliases)
    max_value_len = min(max_value_len, 60)
    print(f"\n{'ALIAS':<{max_name_len}}  {'VALUE':<{max_value_len}}")
    print("-" * (max_name_len + max_value_len + 2))
    for name, value, _ in sorted_aliases:
        if len(value) > 60:
            value = value[:57] + "..."
        print(f"{name:<{max_name_len}}  {value:<{max_value_len}}")


def main() -> None:
    aliases_file = Path.home() / ".config/bash.d/bash_aliases"
    if len(sys.argv) > 1:
        aliases_file = Path(sys.argv[1])
    print(f"Reading aliases from: {aliases_file}")
    print("-" * 50)
    aliases = parse_aliases(aliases_file)
    if not aliases:
        print("No aliases found in file")
        sys.exit(0)
    print(f"Found {len(aliases)} alias(es)")
    print("\n--- BEFORE SORTING (first 10 by value) ---")
    display_aliases(aliases, limit=10)
    print("\n" + "-" * 50)
    response = input(f"Sort all {len(aliases)} aliases by value? [y/N]: ").strip().lower()
    if response != "y":
        print("Operation cancelled")
        sys.exit(0)
    write_sorted_aliases(aliases, aliases_file, create_backup=True)
    print("\n--- AFTER SORTING (first 10 by value) ---")
    sorted_preview = sorted(aliases, key=lambda x: x[1])[:10]
    display_aliases(sorted_preview)
    print("\n✓ Done! Reload your shell to use the sorted aliases:")
    print("source ~/.bashrc")
    print("  # or")
    print("  exec $SHELL")


if __name__ == "__main__":
    main()
