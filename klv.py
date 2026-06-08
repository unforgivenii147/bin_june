#!/data/data/com.termux/files/usr/bin/python

"""
Script to detect and keep only the latest version of wheel or deb files in current directory recursively.
"""

import re
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from packaging import version as pkg_version


def parse_wheel_version(filename: str) -> Optional[Tuple[str, str]]:
    """
    Parse wheel filename to extract package name and version.
    Wheel naming convention: {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
    """
    # Remove .whl extension
    name = filename[:-4]

    # Split by '-' but the version contains numbers and dots
    parts = name.split("-")

    if len(parts) < 5:
        return None

    # Package name is the first part(s) until we hit something that looks like a version
    pkg_name_parts = []
    version_parts = []
    found_version = False

    for i, part in enumerate(parts):
        # Version typically starts with a digit or common version indicators
        if not found_version and (re.match(r"^\d", part) or part.lower() in ["v", "ver", "version"]):
            found_version = True
            version_parts.append(part)
        elif not found_version:
            pkg_name_parts.append(part)
        else:
            # Check if we're still in version part (before python/abi/platform tags)
            # Wheel format: name-version[-build]-python-abi-platform.whl
            # We stop at the 3 parts before the end (python, abi, platform tags)
            remaining_parts = len(parts) - i
            if remaining_parts <= 3:  # We've reached python/abi/platform tags
                break
            version_parts.append(part)

    if pkg_name_parts and version_parts:
        pkg_name = "-".join(pkg_name_parts)
        version = "-".join(version_parts)
        return pkg_name, version

    return None


def parse_deb_version(filename: str) -> Optional[Tuple[str, str]]:
    """
    Parse deb filename to extract package name and version.
    Deb naming convention: {package}_{version}_{architecture}.deb
    """
    # Remove .deb extension
    name = filename[:-4]

    # Split by '_' - deb format: name_version_arch
    parts = name.split("_")

    if len(parts) >= 2:
        pkg_name = parts[0]
        version = parts[1]
        return pkg_name, version

    return None


def compare_versions(ver1: str, ver2: str) -> int:
    """
    Compare two version strings using packaging.version for proper semantic versioning.
    Returns:
        -1 if ver1 < ver2
        0 if ver1 == ver2
        1 if ver1 > ver2
    """
    try:
        v1 = pkg_version.parse(ver1)
        v2 = pkg_version.parse(ver2)

        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1
        else:
            return 0
    except:
        # Fallback to simple string comparison if packaging.version fails
        if ver1 < ver2:
            return -1
        elif ver1 > ver2:
            return 1
        else:
            return 0


def process_file(file_path: Path, file_type: str) -> Optional[Tuple[str, str, Path]]:
    """
    Process a single file and extract package info.
    """
    try:
        filename = file_path.name

        if file_type == "wheel" and filename.endswith(".whl"):
            parsed = parse_wheel_version(filename)
            if parsed:
                pkg_name, version = parsed
                return (pkg_name, version, file_path)

        elif file_type == "deb" and filename.endswith(".deb"):
            parsed = parse_deb_version(filename)
            if parsed:
                pkg_name, version = parsed
                return (pkg_name, version, file_path)

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

    return None


def scan_directory(directory: Path, file_type: str, check_all: bool = False) -> Dict[str, List[Tuple[str, Path]]]:
    """
    Scan directory recursively for package files.
    Returns dict mapping package name to list of (version, path).
    """
    packages = defaultdict(list)
    extensions = []

    if check_all:
        extensions = [".whl", ".deb"]
    else:
        if file_type == "wheel":
            extensions = [".whl"]
        elif file_type == "deb":
            extensions = [".deb"]

    # Collect all files to process
    files_to_process = []
    for ext in extensions:
        files_to_process.extend(directory.rglob(f"*{ext}"))

    print(f"Found {len(files_to_process)} files to process...")

    # Process files concurrently
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for file_path in files_to_process:
            if file_path.suffix == ".whl":
                future = executor.submit(process_file, file_path, "wheel")
            elif file_path.suffix == ".deb":
                future = executor.submit(process_file, file_path, "deb")
            else:
                continue
            futures[future] = file_path

        for future in as_completed(futures):
            result = future.result()
            if result:
                pkg_name, version, file_path = result
                packages[pkg_name].append((version, file_path))

    return packages


def get_latest_version(versions: List[Tuple[str, Path]]) -> Tuple[str, Path]:
    """
    Get the latest version from a list of (version, path) tuples.
    """
    if not versions:
        return None

    latest = versions[0]
    for version, path in versions[1:]:
        if compare_versions(version, latest[0]) > 0:
            latest = (version, path)
    return latest


def keep_latest_versions(packages: Dict[str, List[Tuple[str, Path]]], dry_run: bool = False):
    """
    Keep only the latest version for each package, delete older ones.
    """
    total_deleted = 0

    for pkg_name, versions in packages.items():
        if len(versions) <= 1:
            continue

        # Find the latest version manually using proper comparison
        latest_version, latest_path = get_latest_version(versions)

        print(f"\nPackage: {pkg_name}")
        print(f"  Latest version: {latest_version} - {latest_path.name}")
        print(f"  Total versions found: {len(versions)}")

        # Delete older versions
        for version, file_path in versions:
            if file_path == latest_path:
                continue

            if dry_run:
                print(f"  Would delete: {version} - {file_path.name}")
            else:
                try:
                    file_path.unlink()
                    print(f"  Deleted: {version} - {file_path.name}")
                    total_deleted += 1
                except Exception as e:
                    print(f"  Error deleting {file_path.name}: {e}")

    return total_deleted


def main():
    parser = argparse.ArgumentParser(
        description="Detect and keep only the latest version of package files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Mutually exclusive group for file type selection
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-d", "--deb", action="store_true", help="Check .deb files")
    group.add_argument("-w", "--wheel", action="store_true", help="Check .whl files")
    group.add_argument("-a", "--all", action="store_true", help="Check all package types (.whl and .deb)")

    parser.add_argument("--dry-run", action="store_true", help="Simulate deletion without actually removing files")
    parser.add_argument("--dir", type=str, default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed information about each file")

    args = parser.parse_args()

    # Default to wheel if no option specified
    if not (args.deb or args.wheel or args.all):
        args.wheel = True

    scan_dir = Path(args.dir).resolve()
    if not scan_dir.exists():
        print(f"Error: Directory '{scan_dir}' does not exist")
        return 1

    # Determine file type to scan
    if args.all:
        file_type = "all"
    elif args.deb:
        file_type = "deb"
    else:
        file_type = "wheel"

    print(f"Scanning directory: {scan_dir}")
    print(f"File type: {file_type}")
    if args.dry_run:
        print("DRY RUN MODE - No files will be deleted")
    print("-" * 50)

    # Scan for packages
    packages = scan_directory(scan_dir, file_type, args.all)

    if not packages:
        print("No matching package files found.")
        return 0

    # Display found packages
    print(f"\nFound {len(packages)} package(s):")
    for pkg_name, versions in packages.items():
        print(f"  {pkg_name}: {len(versions)} version(s)")
        if args.verbose and len(versions) > 1:
            for version, path in versions:
                print(f"    - {version}: {path.name}")

    # Keep only latest versions
    print("\n" + "=" * 50)
    total_deleted = keep_latest_versions(packages, args.dry_run)

    print("\n" + "=" * 50)
    if total_deleted == 0:
        print("No files to delete. All packages have only one version.")
    elif args.dry_run:
        print(f"Dry run complete. Would delete {total_deleted} file(s).")
    else:
        print(f"Cleanup complete. Deleted {total_deleted} file(s).")

    return 0


if __name__ == "__main__":
    exit(main())
