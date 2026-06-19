#!/data/data/com.termux/files/usr/bin/python
import os
import glob
import re
from pathlib import Path


def should_skip(so_path):
    """Check if file should be skipped"""
    # Skip if it's a symlink
    if so_path.is_symlink():
        return True

    name = so_path.name

    # Skip if already has .0 or .1 at the end
    if name.endswith(".0") or name.endswith(".1"):
        return True

    # Skip if it already has version pattern like .so.0.0.0
    if re.search(r"\.so\.\d+(\.\d+)+$", name):
        return True

    return False


def get_base_name(so_path):
    """Extract base library name without version suffixes"""
    name = so_path.name

    # Remove .so and any trailing version numbers
    # e.g., libsentencepiece.so.0.0.0 -> libsentencepiece.so
    match = re.match(r"(.+\.so)(?:\.\d+)*$", name)
    if match:
        return match.group(1)
    return name


def create_symlinks():
    # Get the user's local lib directory
    lib_dir = Path.home() / ".local" / "lib"

    if not lib_dir.exists():
        print(f"Error: {lib_dir} does not exist")
        return

    # Find all .so files and .so.* files
    so_files = glob.glob(str(lib_dir / "*.so"))
    so_files.extend(glob.glob(str(lib_dir / "*.so.*")))

    # Track processed base libraries to avoid duplicates
    processed_bases = set()

    for so_file in sorted(so_files):  # Sort for consistent ordering
        so_path = Path(so_file)

        # Skip if conditions met
        if should_skip(so_path):
            continue

        # Get absolute path
        abs_path = so_path.resolve()

        # Get base name (without version suffixes)
        base_name = get_base_name(so_path)

        # Skip if we've already processed this base library
        if base_name in processed_bases:
            continue
        processed_bases.add(base_name)

        # Create symlinks for .so.0 and .so.1
        for version in [".0", ".1"]:
            symlink_name = base_name + version
            symlink_path = lib_dir / symlink_name

            # Check if symlink already points to correct target
            if symlink_path.is_symlink():
                target = os.readlink(symlink_path)
                if target == base_name or Path(target).resolve() == abs_path:
                    print(f"Exists: {symlink_path} -> {target} (correct)")
                    continue
                else:
                    # Remove incorrect symlink
                    symlink_path.unlink()

            # Remove if it's a regular file
            elif symlink_path.exists():
                symlink_path.unlink()

            # Create the symlink
            try:
                # Use relative path for symlink
                relative_path = base_name
                symlink_path.symlink_to(relative_path)
                print(f"Created: {symlink_path} -> {relative_path}")
            except Exception as e:
                print(f"Failed to create {symlink_path}: {e}")


if __name__ == "__main__":
    create_symlinks()
