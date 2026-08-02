#!/data/data/com.termux/files/home/.local/bin/python
"""
Remove old versions of Python package metadata files, keeping only the latest version.
Uses pathlib and parallel processing for efficiency.
"""

import re
import shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict
from packaging.version import Version, InvalidVersion
from typing import Dict, List, Tuple
import argparse


def parse_filename(filepath: Path) -> Tuple[str, Version, Path]:
    """
    Parse a metadata filename to extract package name and version.

    Args:
        filepath: Path to metadata file

    Returns:
        Tuple of (package_name, version_object, filepath)
    """
    # Remove .metadata extension
    name = filepath.stem

    # Handle special case with underscore (like aiohttp-jinja2-1_1.6.metadata)
    # This appears to be an alternative version format
    # We'll normalize underscores in version to dots for comparison

    # Try to extract version using regex
    # Pattern: package-name-version where version is at the end
    # Version can contain digits, dots, and sometimes underscores
    match = re.match(r"^(.+?)-(\d[\d._]*[a-zA-Z]*[\d]*)$", name)

    if not match:
        print(f"Warning: Could not parse version from {filepath.name}")
        return (name, Version("0.0.0"), filepath)

    pkg_name = match.group(1)
    version_str = match.group(2)

    # Normalize version string: replace underscores with dots for comparison
    # But keep the original filename for deletion
    normalized_version = version_str.replace("_", ".")

    try:
        version = Version(normalized_version)
    except InvalidVersion:
        print(f"Warning: Invalid version '{version_str}' in {filepath.name}")
        version = Version("0.0.0")

    return (pkg_name.lower(), version, filepath)


def normalize_package_name(name: str) -> str:
    """
    Normalize package name for comparison.
    PEP 503 normalization: lowercase, replace [-_.] with -
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def find_metadata_files(directory: Path) -> List[Path]:
    """
    Find all .metadata files in the given directory.

    Args:
        directory: Directory to search

    Returns:
        List of Path objects for metadata files
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    return list(directory.glob("*.metadata"))


def process_file_batch(files: List[Path]) -> Dict[str, List[Tuple[Version, Path]]]:
    """
    Process a batch of files and group by package name.

    Args:
        files: List of file paths to process

    Returns:
        Dictionary mapping package names to list of (version, path) tuples
    """
    packages = defaultdict(list)

    for filepath in files:
        pkg_name, version, path = parse_filename(filepath)
        normalized_name = normalize_package_name(pkg_name)
        packages[normalized_name].append((version, path))

    return packages


def find_old_versions(package_files: List[Tuple[Version, Path]]) -> List[Path]:
    """
    Find old versions of a package, keeping only the latest.

    Args:
        package_files: List of (version, path) tuples for a package

    Returns:
        List of paths to delete (all except the latest version)
    """
    if len(package_files) <= 1:
        return []

    # Sort by version, latest first
    sorted_files = sorted(package_files, key=lambda x: x[0], reverse=True)

    # Keep the first (latest), remove the rest
    latest = sorted_files[0]
    old_versions = sorted_files[1:]

    print(f"  Keeping: {latest[1].name} (v{latest[0]})")
    for version, path in old_versions:
        print(f"  Removing: {path.name} (v{version})")

    return [path for version, path in old_versions]


def merge_results(results: List[Dict[str, List[Tuple[Version, Path]]]]) -> Dict[str, List[Tuple[Version, Path]]]:
    """
    Merge results from multiple batches.

    Args:
        results: List of dictionaries from batch processing

    Returns:
        Merged dictionary of package versions
    """
    merged = defaultdict(list)

    for result in results:
        for pkg_name, versions in result.items():
            merged[pkg_name].extend(versions)

    return merged


def delete_files(paths: List[Path], dry_run: bool = True, backup_dir: Path = None):
    """
    Delete or move files.

    Args:
        paths: List of paths to delete
        dry_run: If True, only print what would be deleted
        backup_dir: If provided, move files here instead of deleting
    """
    for path in paths:
        if dry_run:
            print(f"  [DRY RUN] Would delete: {path.name}")
        elif backup_dir:
            backup_path = backup_dir / path.name
            shutil.move(str(path), str(backup_path))
            print(f"  Moved to backup: {path.name}")
        else:
            path.unlink()
            print(f"  Deleted: {path.name}")


def main():
    parser = argparse.ArgumentParser(description="Remove old versions of Python package metadata files")
    parser.add_argument(
        "directory", nargs="?", default=".", help="Directory containing metadata files (default: current directory)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    parser.add_argument("--backup-dir", type=str, help="Move old files to backup directory instead of deleting")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes (default: CPU count)")
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Number of files to process per batch (default: 100)"
    )

    args = parser.parse_args()

    # Setup directories
    metadata_dir = Path(args.directory)

    if not metadata_dir.exists():
        print(f"Error: Directory '{metadata_dir}' does not exist")
        return 1

    backup_dir = None
    if args.backup_dir:
        backup_dir = Path(args.backup_dir)
        if not args.dry_run:
            backup_dir.mkdir(parents=True, exist_ok=True)

    # Find all metadata files
    print(f"Scanning directory: {metadata_dir}")
    all_files = find_metadata_files(metadata_dir)
    print(f"Found {len(all_files)} metadata files")

    if not all_files:
        print("No metadata files found")
        return 0

    # Split files into batches for parallel processing
    batch_size = max(1, args.batch_size)
    batches = [all_files[i : i + batch_size] for i in range(0, len(all_files), batch_size)]

    # Process batches in parallel
    print(f"Processing {len(batches)} batches using {args.workers or 'all available'} workers...")

    batch_results = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_to_batch = {executor.submit(process_file_batch, batch): i for i, batch in enumerate(batches)}

        for future in as_completed(future_to_batch):
            batch_idx = future_to_batch[future]
            try:
                result = future.result()
                batch_results.append(result)
                print(f"  Batch {batch_idx + 1}/{len(batches)} completed")
            except Exception as e:
                print(f"  Error processing batch {batch_idx + 1}: {e}")

    # Merge results from all batches
    print("\nMerging results...")
    all_packages = merge_results(batch_results)

    # Find old versions for each package
    print(f"\nProcessing {len(all_packages)} unique packages...")
    files_to_delete = []

    for pkg_name, versions in sorted(all_packages.items()):
        if len(versions) > 1:
            print(f"\nPackage: {pkg_name} ({len(versions)} versions)")
            old_files = find_old_versions(versions)
            files_to_delete.extend(old_files)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Total metadata files: {len(all_files)}")
    print(f"  Unique packages: {len(all_packages)}")
    print(f"  Files to remove: {len(files_to_delete)}")

    if files_to_delete:
        print(f"\n{'=' * 60}")
        print(f"Removing {len(files_to_delete)} old version files...")
        delete_files(files_to_delete, dry_run=args.dry_run, backup_dir=backup_dir)

        if args.dry_run:
            print("\nThis was a dry run. Use without --dry-run to actually delete files.")
    else:
        print("\nNo duplicate versions found. All packages have single versions.")

    return 0


if __name__ == "__main__":
    exit(main())
