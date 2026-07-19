#!/data/data/com.termux/files/usr/bin/env python
"""
Report Python packages installed in both user and system site directories.
Uses pathlib for path handling and concurrent.futures for parallel processing.
"""

from __future__ import annotations

import concurrent.futures
import pathlib
import site
import sys
from typing import Dict, List, Tuple


def get_site_directories() -> Tuple[List[pathlib.Path], List[pathlib.Path]]:
    """
    Get system and user site-packages directories.

    Returns:
        Tuple of (system_site_dirs, user_site_dirs)
    """
    # Get all site-packages directories
    site_dirs = [pathlib.Path(p) for p in site.getsitepackages()]

    # Get user site-packages directory
    user_site = pathlib.Path(site.getusersitepackages())

    # Separate system and user directories
    system_site_dirs = [d for d in site_dirs if d != user_site]
    user_site_dirs = [user_site] if user_site.exists() else []

    return system_site_dirs, user_site_dirs


def scan_directory_for_packages(directory: pathlib.Path) -> Dict[str, pathlib.Path]:
    """
    Scan a directory for installed packages.

    Args:
        directory: Path to scan for packages

    Returns:
        Dictionary mapping package names to their locations
    """
    packages = {}

    if not directory.exists():
        return packages

    try:
        for item in directory.iterdir():
            if item.is_dir():
                # Check for regular packages
                if (item / "__init__.py").exists():
                    packages[item.name] = item
                # Check for namespace packages
                elif item.suffix == ".dist-info" or item.suffix == ".egg-info":
                    # Extract package name from dist-info/egg-info directory
                    pkg_name = item.name.split("-")[0]
                    packages[pkg_name] = item
            elif item.is_file():
                # Check for single-file modules
                if item.suffix == ".py":
                    packages[item.stem] = item
                # Check for .dist-info and .egg-info files
                elif (item.suffix == ".dist-info" or item.suffix == ".egg-info") and item.is_dir():
                    pkg_name = item.name.split("-")[0]
                    packages[pkg_name] = item

    except PermissionError:
        print(f"Warning: Permission denied accessing {directory}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Error scanning {directory}: {e}", file=sys.stderr)

    return packages


def find_duplicate_packages(
    system_packages: Dict[str, pathlib.Path], user_packages: Dict[str, pathlib.Path]
) -> Dict[str, Tuple[pathlib.Path, pathlib.Path]]:
    """
    Find packages that exist in both system and user directories.

    Args:
        system_packages: Packages from system directories
        user_packages: Packages from user directories

    Returns:
        Dictionary mapping package names to (system_location, user_location) tuples
    """
    duplicates = {}
    common_packages = set(system_packages.keys()) & set(user_packages.keys())

    for pkg_name in sorted(common_packages):
        duplicates[pkg_name] = (system_packages[pkg_name], user_packages[pkg_name])

    return duplicates


def process_system_directories(system_dirs: List[pathlib.Path]) -> Dict[str, pathlib.Path]:
    """
    Process system directories in parallel.

    Args:
        system_dirs: List of system site-package directories

    Returns:
        Combined dictionary of all system packages
    """
    system_packages = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(system_dirs) or 1) as executor:
        future_to_dir = {
            executor.submit(scan_directory_for_packages, directory): directory for directory in system_dirs
        }

        for future in concurrent.futures.as_completed(future_to_dir):
            directory = future_to_dir[future]
            try:
                packages = future.result()
                system_packages.update(packages)
            except Exception as e:
                print(f"Error processing {directory}: {e}", file=sys.stderr)

    return system_packages


def process_user_directories(user_dirs: List[pathlib.Path]) -> Dict[str, pathlib.Path]:
    """
    Process user directories in parallel.

    Args:
        user_dirs: List of user site-package directories

    Returns:
        Combined dictionary of all user packages
    """
    user_packages = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(user_dirs) or 1) as executor:
        future_to_dir = {executor.submit(scan_directory_for_packages, directory): directory for directory in user_dirs}

        for future in concurrent.futures.as_completed(future_to_dir):
            directory = future_to_dir[future]
            try:
                packages = future.result()
                user_packages.update(packages)
            except Exception as e:
                print(f"Error processing {directory}: {e}", file=sys.stderr)

    return user_packages


def analyze_package_versions(
    package_name: str, system_location: pathlib.Path, user_location: pathlib.Path
) -> Dict[str, str]:
    """
    Try to determine the versions of a package in both locations.

    Args:
        package_name: Name of the package
        system_location: System installation location
        user_location: User installation location

    Returns:
        Dictionary with version information
    """
    versions = {"system_version": "unknown", "user_version": "unknown"}

    # Try to find version information in dist-info or egg-info directories
    for location_type, location in [("system", system_location), ("user", user_location)]:
        try:
            # Check if the location itself is a dist-info/egg-info directory
            if location.suffix in [".dist-info", ".egg-info"]:
                # Try to find METADATA or PKG-INFO file
                metadata_files = ["METADATA", "PKG-INFO"]
                for metadata_file in metadata_files:
                    metadata_path = location / metadata_file
                    if metadata_path.exists():
                        with open(metadata_path) as f:
                            for line in f:
                                if line.startswith("Version:"):
                                    version_key = f"{location_type}_version"
                                    versions[version_key] = line.split(":", 1)[1].strip()
                                    break
            else:
                # Look for dist-info directory in the package directory
                parent_dir = location.parent if location.is_file() else location
                dist_info_dirs = list(parent_dir.glob(f"{package_name}-*.dist-info"))
                if not dist_info_dirs:
                    dist_info_dirs = list(parent_dir.glob(f"{package_name}-*.egg-info"))

                for dist_dir in dist_info_dirs[:1]:  # Just check first one
                    metadata_path = dist_dir / "METADATA"
                    if not metadata_path.exists():
                        metadata_path = dist_dir / "PKG-INFO"

                    if metadata_path.exists():
                        with open(metadata_path) as f:
                            for line in f:
                                if line.startswith("Version:"):
                                    version_key = f"{location_type}_version"
                                    versions[version_key] = line.split(":", 1)[1].strip()
                                    break
        except Exception:
            pass

    return versions


def main():
    """Main function to find and report duplicate packages."""
    print("Python Package Duplicate Checker")
    print("=" * 50)

    # Get site directories
    try:
        system_dirs, user_dirs = get_site_directories()
    except Exception as e:
        print(f"Error getting site directories: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nSystem site directories:")
    for d in system_dirs:
        print(f"  - {d}")

    print(f"\nUser site directory:")
    for d in user_dirs:
        print(f"  - {d}")

    if not user_dirs:
        print("\nNo user site-packages directory found.")
        return

    print("\nScanning for packages...")

    # Process directories in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        system_future = executor.submit(process_system_directories, system_dirs)
        user_future = executor.submit(process_user_directories, user_dirs)

        system_packages = system_future.result()
        user_packages = user_future.result()

    # Find duplicates
    duplicates = find_duplicate_packages(system_packages, user_packages)

    # Report results
    print(f"\nResults:")
    print(f"  System packages found: {len(system_packages)}")
    print(f"  User packages found: {len(user_packages)}")
    print(f"  Duplicate packages: {len(duplicates)}")

    if duplicates:
        print("\n" + "=" * 80)
        print("Packages installed in BOTH system and user directories:")
        print("=" * 80)

        for pkg_name, (system_loc, user_loc) in duplicates.items():
            versions = analyze_package_versions(pkg_name, system_loc, user_loc)

            print(f"\n📦 {pkg_name}")
            print(f"   System:  {system_loc}")
            if versions["system_version"] != "unknown":
                print(f"            Version: {versions['system_version']}")

            print(f"   User:    {user_loc}")
            if versions["user_version"] != "unknown":
                print(f"            Version: {versions['user_version']}")

            if versions["system_version"] != "unknown" and versions["user_version"] != "unknown":
                if versions["system_version"] != versions["user_version"]:
                    print(f"   ⚠️  Version mismatch!")
    else:
        print("\n✅ No duplicate packages found.")

    print("\n" + "=" * 80)
    print("Note: Having packages in both locations can lead to confusion about")
    print("which version is being used. Consider removing user installations of")
    print("packages that are already available system-wide.")


if __name__ == "__main__":
    main()
