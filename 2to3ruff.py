#!/data/data/com.termux/files/usr/bin/python


"""
Convert Python 2 print statements to Python 3, handling syntax errors gracefully.
"""

import subprocess
import sys
import os
import re
import tempfile
from pathlib import Path


def fix_print_statements_manually(content):
    lines = content.split("\n")
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if re.search(r"\bprint\s+", line) and not is_in_string(line, "print"):
            if ">>" in line:
                line = re.sub("print\\s+>>\\s*(\\w+)\\s*,\\s*(.+?)(?:\\s*#.*)?$", "print(\\2, file=\\1)", line)
            else:
                line = re.sub("print\\s+(.+?)(?:\\s*#.*)?$", "print(\\1)", line)
            new_lines.append(line)
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


def is_in_string(line, text):
    in_string = False
    quote_char = None
    for i, char in enumerate(line):
        if char in ('"', "'") and (i == 0 or line[i - 1] != "\\"):
            if not in_string:
                in_string = True
                quote_char = char
            elif char == quote_char:
                in_string = False
                quote_char = None
        elif in_string and text in line[i - len(text) : i + 1]:
            return True
    return False


def convert_with_2to3(file_path, dry_run=False):
    try:
        cmd = ["2to3", "-f", "print", file_path]
        if not dry_run:
            cmd = ["2to3", "-f", "print", "-w", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode == 0
    except FileNotFoundError:
        print("⚠️  2to3 not found. Falling back to manual conversion...")
        return False


def convert_file_with_fallback(file_path, dry_run=False):
    print(f"\n📝 Processing: {file_path}")
    print("  Trying 2to3...")
    if convert_with_2to3(file_path, dry_run):
        print("  ✅ Converted with 2to3")
        return True
    print("  Trying manual conversion...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        fixed_content = fix_print_statements_manually(content)
        if fixed_content != content:
            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(fixed_content)
                print(f"  ✅ Manual conversion applied")
                result = subprocess.run(
                    ["ruff", "check", "--fix", "--select", "UP010", file_path], capture_output=True, text=True
                )
                if result.returncode == 0:
                    print(f"  ✅ Ruff applied additional fixes")
                return True
            else:
                print(f"  📝 Would convert {file_path}")
                return True
        else:
            print(f"  ⚠️  Could not automatically convert {file_path}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def convert_directory(directory, dry_run=False):
    python_files = list(Path(directory).rglob("*.py"))
    if not python_files:
        print(f"⚠️  No Python files found in {directory}")
        return
    print(f"📁 Found {len(python_files)} Python files\n")
    print("=" * 60)
    success_count = 0
    for py_file in python_files:
        if convert_file_with_fallback(str(py_file), dry_run):
            success_count += 1
    print("\n" + "=" * 60)
    print(f"✅ Converted {success_count}/{len(python_files)} files successfully")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Python 2 print statements to Python 3",
        epilog="Handles files that Ruff can't parse due to syntax errors",
    )
    parser.add_argument("path", help="File or directory to convert")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    parser.add_argument("--use-2to3", action="store_true", help="Only use 2to3 (skip manual conversion)")
    args = parser.parse_args()
    if not os.path.exists(args.path):
        print(f"❌ Path not found: {args.path}")
        sys.exit(1)
    if os.path.isfile(args.path):
        convert_file_with_fallback(args.path, args.dry_run)
    else:
        convert_directory(args.path, args.dry_run)


if __name__ == "__main__":
    main()
