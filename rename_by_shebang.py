#!/data/data/com.termux/files/usr/bin/python

"""
Rename files in current directory based on their shebang line.
Optimized for Termux environment.
"""

import os
import re
import shutil
from pathlib import Path

SHEBANG_MAPPING = {
    r"#!/data/data/com.termux/files/usr/bin/python3?": ".py",
    r"#!/data/data/com.termux/files/usr/bin/env python3?": ".py",
    r"#!/usr/bin/env python": ".py",
    r"#!/usr/bin/python": ".py",
    r"#!/data/data/com.termux/files/usr/bin/env sh": ".sh",
    r"#!/data/data/com.termux/files/usr/bin/bash": ".sh",
    r"#!/data/data/com.termux/files/usr/bin/sh": ".sh",
    r"#!/data/data/com.termux/files/usr/bin/env bash": ".sh",
    r"#!/usr/bin/env bash": ".sh",
    r"#!/bin/bash": ".sh",
    r"#!/bin/sh": ".sh",
    r"#!/data/data/com.termux/files/usr/bin/node": ".js",
    r"#!/data/data/com.termux/files/usr/bin/env node": ".js",
    r"#!/usr/bin/env node": ".js",
    r"#!/usr/bin/node": ".js",
    r"#!/data/data/com.termux/files/usr/bin/ruby": ".rb",
    r"#!/data/data/com.termux/files/usr/bin/env ruby": ".rb",
    r"#!/usr/bin/env ruby": ".rb",
    r"#!/usr/bin/ruby": ".rb",
    r"#!/data/data/com.termux/files/usr/bin/perl": ".pl",
    r"#!/data/data/com.termux/files/usr/bin/env perl": ".pl",
    r"#!/usr/bin/env perl": ".pl",
    r"#!/usr/bin/perl": ".pl",
    r"#!/data/data/com.termux/files/usr/bin/lua": ".lua",
    r"#!/data/data/com.termux/files/usr/bin/env lua": ".lua",
    r"#!/usr/bin/env lua": ".lua",
    r"#!/usr/bin/lua": ".lua",
    r"#!/data/data/com.termux/files/usr/bin/php": ".php",
    r"#!/data/data/com.termux/files/usr/bin/env php": ".php",
    r"#!/usr/bin/env php": ".php",
    r"#!/usr/bin/php": ".php",
    r"#!/data/data/com.termux/files/usr/bin/Rscript": ".r",
    r"#!/usr/bin/env Rscript": ".r",
    r"#!/usr/bin/Rscript": ".r",
    r"#!/data/data/com.termux/files/usr/bin/fish": ".fish",
    r"#!/data/data/com.termux/files/usr/bin/env fish": ".fish",
    r"#!/usr/bin/env fish": ".fish",
    r"#!/usr/bin/fish": ".fish",
    r"#!/usr/bin/awk": ".awk",
    r"#!/usr/bin/env awk": ".awk",
    r"#!/usr/bin/sed": ".sed",
}


def get_shebang(file_path):
    """Read the first line of a file and check for shebang."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if first_line.startswith("#!"):
                return first_line
    except (UnicodeDecodeError, IOError):
        pass
    return None


def get_extension_from_shebang(shebang):
    """Match shebang to appropriate extension."""
    for pattern, extension in SHEBANG_MAPPING.items():
        if re.match(pattern, shebang):
            return extension
    return None


def rename_file(old_path, new_path):
    """Rename a file, handling name conflicts."""
    if old_path == new_path:
        return False

    counter = 1
    original_new_path = new_path

    while new_path.exists():
        stem = original_new_path.stem
        suffix = original_new_path.suffix
        new_path = original_new_path.parent / f"{stem}_{counter}{suffix}"
        counter += 1

    print(f"  🔄 Renaming: {old_path.name} -> {new_path.name}")
    shutil.move(str(old_path), str(new_path))
    return True


def check_termux():
    """Check if running in Termux and print environment info."""
    termux_prefix = "/data/data/com.termux/files/usr"
    is_termux = os.path.exists(termux_prefix)

    if is_termux:
        print(f"📱 Termux environment detected")
        print(f"   Prefix: {termux_prefix}")
        print(f"   Python: {os.path.realpath('/data/data/com.termux/files/usr/bin/python3')}")
    else:
        print(f"💻 Standard Linux/Unix environment detected")

    return is_termux


def main():
    """Main function to process files in current directory."""
    cwd = Path.cwd()
    renamed_count = 0
    skipped_count = 0
    unknown_count = 0

    is_termux = check_termux()
    print(f"📂 Scanning directory: {cwd}\n")

    files = [f for f in cwd.iterdir() if f.is_file()]

    if not files:
        print("No files found in current directory.")
        return

    for file_path in files:
        if file_path.name.startswith("."):
            continue

        shebang = get_shebang(file_path)
        if not shebang:
            continue

        extension = get_extension_from_shebang(shebang)
        if not extension:
            short_shebang = shebang[:50] + "..." if len(shebang) > 50 else shebang
            print(f"❓ Unknown shebang in: {file_path.name}")
            print(f"   Shebang: {short_shebang}")
            unknown_count += 1
            continue

        old_name = file_path.stem
        if not file_path.suffix:
            new_name = f"{old_name}{extension}"
        elif file_path.suffix != extension:
            new_name = f"{old_name}{extension}"
        else:
            skipped_count += 1
            continue

        new_path = file_path.parent / new_name
        if rename_file(file_path, new_path):
            renamed_count += 1

    print(f"\n{'=' * 50}")
    print(f"📊 Summary:")
    print(f"   ✅ Renamed: {renamed_count} file(s)")
    print(f"   ⏭️  Skipped (already correct): {skipped_count} file(s)")
    if unknown_count:
        print(f"   ❓ Unknown shebangs: {unknown_count} file(s)")
    print(f"{'=' * 50}")

    if unknown_count > 0:
        print("\n💡 Tip: You can add new shebang patterns to the SHEBANG_MAPPING dictionary")


def dry_run():
    """Preview changes without actually renaming."""
    cwd = Path.cwd()

    print("🔍 DRY RUN MODE - No files will be renamed\n")
    check_termux()
    print(f"📂 Scanning directory: {cwd}\n")

    for file_path in cwd.iterdir():
        if not file_path.is_file() or file_path.name.startswith("."):
            continue

        shebang = get_shebang(file_path)
        if not shebang:
            continue

        extension = get_extension_from_shebang(shebang)
        if extension and not file_path.suffix == extension:
            new_name = f"{file_path.stem}{extension}"
            print(f"  Would rename: {file_path.name} -> {new_name}")

    print(f"\nRun without '--dry-run' to apply changes.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        dry_run()
    elif len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python rename_by_shebang.py [OPTION]")
        print("Options:")
        print("  --dry-run    Preview changes without renaming")
        print("  --help       Show this help message")
    else:
        response = input("⚠️  This will rename files in the current directory. Continue? (y/N): ")
        if response.lower() == "y":
            main()
        else:
            print("Operation cancelled.")
