#!/data/data/com.termux/files/usr/bin/env python

"""Module for check_system_bin.py."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def calculate_hash(filepath: Path, chunk_size=8192):
    sha256 = hashlib.sha256()
    try:
        with filepath.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError):
        return None


def get_system_bin_hashes():
    system_bin = Path("/system/bin")
    if not system_bin.exists():
        print("⚠️  /system/bin directory not found!")
        return {}
    hashes = {}
    print("📂 Scanning /system/bin files...")
    for filepath in system_bin.iterdir():
        try:
            if filepath.is_file() or filepath.is_symlink():
                hash_value = calculate_hash(filepath)
                if hash_value:
                    hashes[hash_value] = filepath.name
        except (PermissionError, OSError):
            continue
    print(f"✅ Scanned {len(hashes)} files in /system/bin\n")
    return hashes


def check_and_move_files(system_hashes):
    current_dir = Path.cwd()
    matches_dir = current_dir / "matched_system_files"
    matches_dir.mkdir(exist_ok=True)
    matches = []
    moved = []
    print("🔍 Scanning current directory...")
    for filepath in current_dir.iterdir():
        try:
            if filepath.is_file() and (not filepath.name.startswith(".")):
                if filepath.resolve() == matches_dir.resolve():
                    continue
                hash_value = calculate_hash(filepath)
                if hash_value and hash_value in system_hashes:
                    system_filename = system_hashes[hash_value]
                    matches.append((filepath.name, system_filename))
                    if filepath.name == system_filename:
                        dest_path = matches_dir / filepath.name
                        counter = 1
                        original_dest = dest_path
                        while dest_path.exists():
                            dest_path = original_dest.parent / f"{original_dest.stem}_{counter}{original_dest.suffix}"
                            counter += 1
                        shutil.move(filepath, dest_path)
                        moved.append((filepath.name, dest_path.name))
                        print(f"  📦 Moved: {filepath.name} -> {dest_path.name}")
                    else:
                        print(f"  ⚠️  Hash matches but filename differs: {filepath.name} (system: {system_filename})")
        except (PermissionError, OSError) as e:
            print(f"  ⚠️  Error with {filepath.name}: {e}")
            continue
    return (matches, moved)


def main():
    print("=" * 60)
    print("🔐 File Hash Comparison & Move Tool")
    print("=" * 60)
    system_hashes = get_system_bin_hashes()
    if not system_hashes:
        print("❌ No readable files found in /system/bin")
        return
    matches, moved = check_and_move_files(system_hashes)
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    if matches:
        print(f"⚠️  Found {len(matches)} files with matching hashes:")
        for local_file, system_file in matches:
            status = "✅ MOVED" if local_file == system_file else "❌ Name mismatch"
            print(f"  • {local_file} matches /system/bin/{system_file} - {status}")
        if moved:
            print(f"\n📦 Moved {len(moved)} files to './matched_system_files/' directory:")
            for original, new_name in moved:
                print(f"  • {original} -> {new_name}")
    else:
        print("✅ No matching files found.")
    print("=" * 60)


if __name__ == "__main__":
    main()
