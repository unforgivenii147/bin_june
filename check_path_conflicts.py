#!/data/data/com.termux/files/usr/bin/python


"""
Check if bash aliases and functions conflict with existing scripts and binaries in PATH.
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path


def get_path_dirs() -> list[str]:
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    existing_dirs = [d for d in path_dirs if os.path.exists(d)]
    return existing_dirs


def get_commands_from_path(path_dirs: list[str]):
    commands = {}
    duplicate_commands = defaultdict(list)
    for dir_path in path_dirs:
        try:
            for item in os.listdir(dir_path):
                item_path = os.path.join(dir_path, item)
                if os.path.isfile(item_path) and os.access(item_path, os.X_OK):
                    commands[item] = (item_path, dir_path)
                    duplicate_commands[item].append(dir_path)
        except (PermissionError, OSError):
            continue
    conflicts = {cmd: paths for cmd, paths in duplicate_commands.items() if len(paths) > 1}
    return (commands, conflicts)


def extract_aliases(aliases_file: Path):
    aliases = {}
    alias_pattern = re.compile("^\\s*alias\\s+([a-zA-Z_][a-zA-Z0-9_-]*)\\s*=", re.MULTILINE)
    if not aliases_file.exists():
        return {}
    try:
        with open(aliases_file, "r", encoding="utf-8") as f:
            content = f.read()
            content = re.sub("\\\\\\n", "", content)
            matches = alias_pattern.findall(content)
            for match in matches:
                aliases[match] = True
    except Exception as e:
        print(f"Warning: Could not read aliases file: {e}")
    return aliases


def extract_functions(functions_file: Path):
    functions = {}
    patterns = [
        re.compile("^\\s*([a-zA-Z_][a-zA-Z0-9_-]*)\\s*\\(\\s*\\)\\s*\\{"),
        re.compile("^\\s*function\\s+([a-zA-Z_][a-zA-Z0-9_-]*)\\s*\\{"),
        re.compile("^\\s*function\\s+([a-zA-Z_][a-zA-Z0-9_-]*)\\s*\\(\\s*\\)\\s*\\{"),
    ]
    if not functions_file.exists():
        return {}
    try:
        with open(functions_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for pattern in patterns:
                    match = pattern.search(line)
                    if match:
                        functions[match.group(1)] = True
                        break
    except Exception as e:
        print(f"Warning: Could not read functions file: {e}")
    return functions


def check_conflicts(names, path_commands, name_type: str):
    conflicts = {}
    for name in names:
        if name in path_commands:
            conflicts[name] = path_commands[name]
    return conflicts


def display_results(alias_conflicts, func_conflicts, path_duplicates, path_dirs: list[str]) -> None:
    print("=" * 80)
    print("🔍 PATH CONFLICT ANALYSIS")
    print("=" * 80)
    print(f"\n📁 PATH directories scanned ({len(path_dirs)}):")
    for i, dir_path in enumerate(path_dirs[:10], 1):
        print(f"   {i}. {dir_path}")
    if len(path_dirs) > 10:
        print(f"   ... and {len(path_dirs) - 10} more")
    if path_duplicates:
        print(f"\n⚠️  WARNING: Commands found in multiple PATH locations ({len(path_duplicates)}):")
        for cmd, paths in sorted(path_duplicates.items())[:10]:
            print(f"   • '{cmd}' found in:")
            for path in paths:
                print(f"     - {path}")
        if len(path_duplicates) > 10:
            print(f"   ... and {len(path_duplicates) - 10} more")
    else:
        print("\n✓ No duplicate commands across PATH directories")
    print(f"\n📋 ALIASES ({(len(alias_conflicts) if isinstance(alias_conflicts, dict) else 0)} total)")
    if alias_conflicts:
        print(f"   ❌ Conflicts with PATH commands ({len(alias_conflicts)}):")
        for alias, (full_path, dir_path) in sorted(alias_conflicts.items()):
            print(f"      • '{alias}' -> conflicts with: {full_path}")
        print("\n   💡 Suggestion: Rename these aliases or remove the conflicting binaries")
    else:
        print("   ✓ No conflicts with PATH commands")
    print(f"\n🔧 FUNCTIONS ({(len(func_conflicts) if isinstance(func_conflicts, dict) else 0)} total)")
    if func_conflicts:
        print(f"   ❌ Conflicts with PATH commands ({len(func_conflicts)}):")
        for func, (full_path, dir_path) in sorted(func_conflicts.items()):
            print(f"      • '{func}' -> conflicts with: {full_path}")
        print("\n   💡 Suggestion: Rename these functions or use 'command' prefix")
    else:
        print("   ✓ No conflicts with PATH commands")
    total_conflicts = (len(alias_conflicts) if isinstance(alias_conflicts, dict) else 0) + (
        len(func_conflicts) if isinstance(func_conflicts, dict) else 0
    )
    print("\n" + "=" * 80)
    print(f"📊 SUMMARY: {total_conflicts} total conflict(s) found")
    if total_conflicts > 0:
        print("\n⚠️  Conflicts can cause unexpected behavior!")
        print("   Bash will use aliases/functions over PATH binaries")
        print("   To use the binary instead, prefix with 'command' or '\\'")
        print("   Example: command ls  or  \\ls")
    print("=" * 80)


def suggest_fixes(alias_conflicts, func_conflicts) -> None:
    if not alias_conflicts and (not func_conflicts):
        return
    print("\n🔧 SUGGESTED FIXES:")
    print("-" * 40)
    if alias_conflicts:
        print("\nFor alias conflicts:")
        for conflict in sorted(alias_conflicts.keys())[:5]:
            print(f"   • Rename alias: alias {conflict}_alias='...'")
            print(f"   • Or use in scripts: \\{conflict} (escapes alias)")
    if func_conflicts:
        print("\nFor function conflicts:")
        for conflict in sorted(func_conflicts.keys())[:5]:
            print(f"   • Rename function: {conflict}_func() {{ ... }}")
            print(f"   • Or use in scripts: command {conflict}")
    print("\nTo see all conflicts in detail, run with --verbose flag")


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    check_all = "--all" in sys.argv or "-a" in sys.argv
    config_dir = Path.home() / ".config/bash.d"
    aliases_file = config_dir / "bash_aliases"
    functions_file = config_dir / "bash_functions3"
    print("🔍 Scanning for conflicts between bash aliases/functions and PATH binaries...")
    path_dirs = get_path_dirs()
    path_commands, path_duplicates = get_commands_from_path(path_dirs)
    print(f"✓ Found {len(path_commands)} unique commands in PATH")
    print(f"✓ Found {len(path_duplicates)} commands with duplicates across PATH")
    aliases = extract_aliases(aliases_file)
    functions = extract_functions(functions_file)
    print(f"✓ Found {len(aliases)} aliases")
    print(f"✓ Found {len(functions)} functions")
    alias_conflicts = check_conflicts(aliases.keys(), path_commands, "aliases")
    func_conflicts = check_conflicts(functions.keys(), path_commands, "functions")
    display_results(alias_conflicts, func_conflicts, path_duplicates, path_dirs)
    if verbose:
        suggest_fixes(alias_conflicts, func_conflicts)
    if alias_conflicts or func_conflicts:
        sys.exit(1)
    else:
        print("\n✅ No conflicts detected! Your aliases and functions are safe.")
        sys.exit(0)


if __name__ == "__main__":
    main()
