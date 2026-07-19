#!/data/data/com.termux/files/usr/bin/env python

"""
Check for duplicate function names in bash functions file.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def extract_function_names(filepath: Path):
    functions = []
    patterns = [
        re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*\(\s*\)\s*\{"),
        re.compile(r"^\s*function\s+([a-zA-Z_][a-zA-Z0-9_-]*)\s*\{"),
        re.compile(r"^\s*function\s+([a-zA-Z_][a-zA-Z0-9_-]*)\s*\(\s*\)\s*\{"),
    ]
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                continue
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    func_name = match.group(1)
                    functions.append((func_name, line_num, line.rstrip()))
                    break
    except FileNotFoundError:
        print(f"Error: Functions file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    return functions


def find_duplicates(functions):
    name_counts = Counter(name for name, _, _ in functions)
    duplicates = {name: count for name, count in name_counts.items() if count > 1}
    return duplicates


def display_results(functions, duplicates, filepath: Path) -> bool:
    if not duplicates:
        print("✓ No duplicate function names found!")
        print(f"✓ Total unique functions: {len({name for name, _, _ in functions})}")
        return True
    print(f"✗ Found {len(duplicates)} function name(s) defined multiple times:")
    print("=" * 60)
    for dup_name, count in sorted(duplicates.items()):
        print(f"\n📌 Duplicate function: '{dup_name}' (defined {count} times)")
        print("-" * 40)
        occurrences = [(line_num, line) for name, line_num, line in functions if name == dup_name]
        for idx, (line_num, line) in enumerate(occurrences, 1):
            print(f"  {idx}. Line {line_num}: {line}")
    print("\n" + "=" * 60)
    return False


def show_statistics(functions, duplicates) -> None:
    total_definitions = len(functions)
    unique_functions = len({name for name, _, _ in functions})
    duplicate_count = len(duplicates)
    duplicate_definitions = sum(duplicates.values()) - len(duplicates)
    print("\n📊 Statistics:")
    print(f"   Total function definitions: {total_definitions}")
    print(f"   Unique function names: {unique_functions}")
    print(f"   Functions with duplicates: {duplicate_count}")
    print(f"   Extra duplicate definitions: {duplicate_definitions}")
    if unique_functions > 0:
        duplication_rate = duplicate_definitions / unique_functions * 100
        print(f"   Duplication rate: {duplication_rate:.1f}%")


def interactive_fix(duplicates, functions, filepath: Path) -> None:
    if not duplicates:
        return
    print("\n🔧 Would you like to fix duplicates interactively?")
    response = input("   Review and remove duplicates? [y/N]: ").strip().lower()
    if response != "y":
        print("   Skipping interactive fix.")
        return
    backup_path = f"{filepath}.backup"
    try:
        from shutil import copy2

        copy2(filepath, backup_path)
        print(f"   ✓ Backup created: {backup_path}")
    except Exception as e:
        print(f"   ⚠ Warning: Could not create backup: {e}")
    print("\n   Instructions for fixing duplicates:")
    print("   1. Review the duplicate functions listed above")
    print("   2. Decide which definition(s) to keep")
    print("   3. Remove or comment out the duplicate definitions")
    print(f"   4. Edit the file: {filepath}")
    print("\n   Tip: Use 'keep' to mark a definition to keep, 'remove' to mark for deletion")
    decisions = {}
    for dup_name in duplicates:
        print(f"\n   --- Function: {dup_name} ---")
        occurrences = [(line_num, line) for name, line_num, line in functions if name == dup_name]
        for idx, (line_num, line) in enumerate(occurrences, 1):
            print(f"   {idx}. Line {line_num}: {line[:80]}")
        while True:
            choice = input(f"   Which one to keep? (1-{len(occurrences)} or 'skip'): ").strip()
            if choice.lower() == "skip":
                decisions[dup_name] = None
                break
            try:
                keep_idx = int(choice) - 1
                if 0 <= keep_idx < len(occurrences):
                    decisions[dup_name] = occurrences[keep_idx][0]
                    to_remove = [occ[0] for i, occ in enumerate(occurrences) if i != keep_idx]
                    print(f"   ✓ Will keep line {occurrences[keep_idx][0]}, remove lines: {to_remove}")
                    break
                else:
                    print(f"   Invalid choice. Enter 1-{len(occurrences)} or 'skip'")
            except ValueError:
                print(f"   Invalid input. Enter 1-{len(occurrences)} or 'skip'")
    print("\n   ✓ Decisions recorded. Edit the file manually to:")
    for dup_name, keep_line in decisions.items():
        if keep_line:
            print(f"     - Keep line {keep_line} for '{dup_name}', remove others")
        else:
            print(f"     - Review '{dup_name}' duplicates manually")


def main():
    functions_file = Path.home() / ".config/bash.d/bash_functions"
    if len(sys.argv) > 1:
        functions_file = Path(sys.argv[1])
    print(f"🔍 Checking for duplicate function names in: {functions_file}")
    print("=" * 60)
    functions = extract_function_names(functions_file)
    if not functions:
        print("\n⚠ No function definitions found in file.")
        print(f"""   Make sure the file contains functions like:
   function_name() {{
       commands
   }}""")
        sys.exit(0)
    duplicates = find_duplicates(functions)
    is_clean = display_results(functions, duplicates, functions_file)
    show_statistics(functions, duplicates)
    if not is_clean:
        print("\n⚠ Duplicate function names can cause unexpected behavior!")
        print("   The last defined function will override previous ones.")
        interactive_fix(duplicates, functions, functions_file)
        sys.exit(1)
    else:
        print("\n✅ File is clean! No duplicate function names found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
