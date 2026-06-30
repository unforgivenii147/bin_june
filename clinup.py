#!/data/data/com.termux/files/usr/bin/python
"""
Cleanup Script for Termux/Linux
Removes Windows, Mac, and common junk/temporary files:
- Windows: .exe, .dll, .msi, .bat, .cmd, .ps1, .vbs, .com, .scr, .cpl
- Mac: .DS_Store, ._* files, .Spotlight-V100, .Trashes, etc.
- Junk: .log, .bak, .pyc, .pyo, .tmp, .temp, .cache
"""

import os
import sys
import argparse
from pathlib import Path

WINDOWS_EXTENSIONS = {".exe", ".dll", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".com", ".scr", ".cpl"}
JUNK_EXTENSIONS = {".save", ".log", ".bak", ".pyc", ".pyo", ".tmp", ".temp", ".cache", ".old", ".swp", ".swo", "~"}
MAC_FILES = {
    ".DS_Store",
    ".localized",
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    ".TemporaryItems",
    ".VolumeIcon.icns",
    ".AppleDouble",
    ".LSOverride",
}
MAC_PREFIX = "._"
SAFE_DIRS = {".git", ".svn", ".hg", "node_modules", "venv", ".venv", "env", "__pycache__"}


def get_size(path):
    total = 0
    try:
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            for item in path.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
    except (PermissionError, OSError):
        pass
    return total


def format_size(bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"


def should_skip_dir(path):
    parts = path.parts
    return any(safe_dir in parts for safe_dir in SAFE_DIRS)


def scan_directory(directory, verbose=False, include_junk=True):
    to_remove = []
    total_size = 0
    try:
        for root, dirs, files in os.walk(directory):
            root_path = Path(root)
            if should_skip_dir(root_path):
                if verbose:
                    print(f"Skipping safe directory: {root_path}")
                continue
            if any(mac_folder in root_path.parts for mac_folder in MAC_FILES):
                if verbose:
                    print(f"Skipping Mac directory: {root_path}")
                continue
            for dir_name in dirs:
                dir_path = root_path / dir_name
                if dir_name in MAC_FILES:
                    to_remove.append(("dir", dir_path))
                    if verbose:
                        print(f"Found Mac directory: {dir_path}")
            for file_name in files:
                file_path = root_path / file_name
                if should_skip_dir(file_path.parent):
                    continue
                if file_name in MAC_FILES or file_name.startswith(MAC_PREFIX):
                    to_remove.append(("file", file_path))
                    if verbose:
                        print(f"Found Mac file: {file_path}")
                    continue
                ext = file_path.suffix.lower()
                if ext in WINDOWS_EXTENSIONS:
                    to_remove.append(("file", file_path))
                    if verbose:
                        print(f"Found Windows file: {file_path}")
                    continue
                if include_junk and ext in JUNK_EXTENSIONS:
                    to_remove.append(("file", file_path))
                    if verbose:
                        print(f"Found junk file: {file_path}")
                    continue
                if include_junk and file_name.endswith("~"):
                    to_remove.append(("file", file_path))
                    if verbose:
                        print(f"Found backup file: {file_path}")
                    continue
    except PermissionError:
        print(f"Permission denied: {directory}", file=sys.stderr)
    except Exception as e:
        print(f"Error scanning {directory}: {e}", file=sys.stderr)
    return to_remove


def clean_files(items, dry_run=False, interactive=True):
    removed = []
    total_size = 0
    skipped = []
    for item_type, path in items:
        if item_type == "dir" and should_skip_dir(path):
            skipped.append(path)
            continue
        try:
            size = get_size(path) if item_type == "dir" else path.stat().st_size
            if interactive and not dry_run:
                response = input(f"Remove {path} ({format_size(size)})? [y/N/q]: ").strip().lower()
                if response == "q":
                    print("Quitting...")
                    break
                elif response != "y":
                    skipped.append(path)
                    continue
            if dry_run:
                removed.append((path, size))
                total_size += size
            else:
                if item_type == "dir":
                    import shutil

                    shutil.rmtree(path)
                    print(f"✓ Removed directory: {path}")
                else:
                    os.remove(path)
                    print(f"✓ Removed file: {path}")
                total_size += size
        except (PermissionError, OSError) as e:
            print(f"✗ Cannot remove {path}: {e}", file=sys.stderr)
            skipped.append(path)
    return removed, total_size, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup script for Termux/Linux - Remove Windows, Mac, and junk files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Scan current directory
  %(prog)s -d                 # Dry run (show what would be removed)
  %(prog)s /sdcard/Download   # Scan specific directory
  %(prog)s -y                 # Auto-remove without confirmation
  %(prog)s --no-junk          # Skip junk files (.log, .bak, .pyc)
  %(prog)s --no-windows       # Skip Windows files
  %(prog)s --no-mac           # Skip Mac files
  %(prog)s -v -d              # Verbose dry run
        """,
    )
    parser.add_argument("path", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output")
    parser.add_argument(
        "-d", "--dry-run", action="store_true", help="Show what would be removed without actually removing"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Auto-confirm removal without prompting (use with caution)"
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Prompt for each file/directory before removal"
    )
    parser.add_argument("--no-windows", action="store_true", help="Skip Windows files")
    parser.add_argument("--no-mac", action="store_true", help="Skip Mac files")
    parser.add_argument("--no-junk", action="store_true", help="Skip junk files (.log, .bak, .pyc, etc.)")
    parser.add_argument("--only-junk", action="store_true", help="Only remove junk files (skip Windows and Mac)")
    args = parser.parse_args()
    target_path = Path(args.path).resolve()
    if not target_path.exists():
        print(f"Error: Path does not exist: {target_path}", file=sys.stderr)
        sys.exit(1)
    if not target_path.is_dir():
        print(f"Error: Path is not a directory: {target_path}", file=sys.stderr)
        sys.exit(1)
    print(f"🧹 Cleanup Script")
    print(f"📁 Scanning: {target_path}")
    print("=" * 60)
    include_junk = not args.no_junk
    if args.only_junk:
        args.no_windows = True
        args.no_mac = True
    items = scan_directory(target_path, args.verbose, include_junk)
    if args.no_windows:
        items = [
            (t, p) for t, p in items if not any(p.suffix.lower() in WINDOWS_EXTENSIONS for ext in WINDOWS_EXTENSIONS)
        ]
    if args.no_mac:
        items = [
            (t, p)
            for t, p in items
            if not (
                p.name in MAC_FILES
                or p.name.startswith(MAC_PREFIX)
                or any(mac_folder in p.parts for mac_folder in MAC_FILES)
            )
        ]
    if args.no_junk:
        items = [(t, p) for t, p in items if not (p.suffix.lower() in JUNK_EXTENSIONS or p.name.endswith("~"))]
    if not items:
        print("\n✨ No removable files found. Directory is clean!")
        return
    windows_count = sum(1 for t, p in items if p.suffix.lower() in WINDOWS_EXTENSIONS)
    mac_count = sum(1 for t, p in items if p.name in MAC_FILES or p.name.startswith(MAC_PREFIX))
    junk_count = sum(1 for t, p in items if p.suffix.lower() in JUNK_EXTENSIONS or p.name.endswith("~"))
    total_size = 0
    for _, path in items:
        total_size += get_size(path) if path.is_dir() else path.stat().st_size
    print(f"\n📊 Found {len(items)} items to remove:")
    print(f"   • Windows files: {windows_count}")
    print(f"   • Mac files: {mac_count}")
    print(f"   • Junk files: {junk_count}")
    print(f"   • Total size: {format_size(total_size)}")
    if args.verbose and items:
        print("\n📋 Items to remove:")
        for item_type, path in items[:20]:
            size = get_size(path) if path.is_dir() else path.stat().st_size
            print(f"   {item_type}: {path} ({format_size(size)})")
        if len(items) > 20:
            print(f"   ... and {len(items) - 20} more items")
    if args.dry_run:
        print("\n🔍 DRY RUN - No files were removed.")
        print(f"   Would free: {format_size(total_size)}")
        return
    if not args.yes and not args.interactive:
        response = input(f"\n⚠️  Remove {len(items)} items? (y/N): ").strip().lower()
        if response != "y":
            print("❌ Cancelled.")
            return
    print("\n🗑️  Removing files...")
    removed, removed_size, skipped = clean_files(items, dry_run=False, interactive=args.interactive)
    print(f"\n✅ Cleanup complete!")
    print(f"   • Removed: {len(removed)} items")
    print(f"   • Freed: {format_size(removed_size)}")
    if skipped:
        print(f"   • Skipped: {len(skipped)} items")
    if args.verbose and skipped:
        print("\nSkipped items:")
        for path in skipped[:10]:
            print(f"   {path}")
        if len(skipped) > 10:
            print(f"   ... and {len(skipped) - 10} more")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user.")
        sys.exit(1)
