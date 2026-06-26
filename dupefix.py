#!/data/data/com.termux/files/usr/bin/python
import pathlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import xxhash
import sys
import shutil


def get_file_hash(filepath):
    """Calculate xxh64 hash of a file."""
    try:
        # Check if file still exists before hashing
        if not filepath.exists():
            return filepath, None

        xxh = xxhash.xxh64()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                xxh.update(chunk)
        return filepath, xxh.hexdigest()
    except (OSError, PermissionError, IOError):
        return filepath, None


def remove_duplicates(root_dir, dry_run=True):
    root = pathlib.Path(root_dir)

    # 1. Group by size
    size_map = defaultdict(list)
    print("Scanning directory tree...")
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            try:
                size_map[path.stat().st_size].append(path)
            except OSError:
                continue

    # Filter: Only keep sizes with more than 1 file
    potential_dups = {size: paths for size, paths in size_map.items() if len(paths) > 1}

    # 2. Hash files in parallel with proper error handling
    files_to_hash = [p for paths in potential_dups.values() for p in paths]
    hash_map = defaultdict(list)

    print(f"Hashing {len(files_to_hash)} potential duplicate files...")

    # Process with as_completed for better error handling
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_file = {executor.submit(get_file_hash, f): f for f in files_to_hash}
        for future in as_completed(future_to_file):
            try:
                filepath, file_hash = future.result(timeout=30)
                if file_hash:
                    hash_map[file_hash].append(filepath)
            except Exception as e:
                print(f"Error processing file: {e}")

    # 3. Identify duplicates and delete
    total_freed = 0
    duplicates_found = 0

    for file_hash, paths in hash_map.items():
        if len(paths) > 1:
            duplicates_found += len(paths) - 1

            # Sort by modification time (oldest first) - but ask user preference
            # Or better: sort by path for deterministic results
            paths.sort(key=lambda p: (p.stat().st_mtime, str(p)))

            # Keep the first one, delete the rest
            to_delete = paths[1:]
            for p in to_delete:
                try:
                    # Double-check file still exists
                    if not p.exists():
                        continue

                    file_size = p.stat().st_size

                    if dry_run:
                        print(f"Would delete: {p} ({file_size} bytes)")
                    else:
                        # Use trash if available, else delete
                        if shutil.which("gio"):  # GNOME trash
                            import subprocess

                            subprocess.run(["gio", "trash", str(p)], check=True)
                        else:
                            p.unlink()
                        total_freed += file_size
                        print(f"Deleted: {p}")
                except OSError as e:
                    print(f"Error deleting {p}: {e}")

    print(f"\nCleanup complete.")
    print(f"Duplicate files found: {duplicates_found}")
    if not dry_run:
        print(f"Total disk space freed: {total_freed / (1024 * 1024):.2f} MB")
    else:
        print(f"Potential space to free: {total_freed / (1024 * 1024):.2f} MB")
        print("Run with dry_run=False to actually delete files.")


if __name__ == "__main__":
    # Change '.' to the specific directory you want to clean
    target_dir = "."

    # Always do a dry run first
    print("DRY RUN - No files will be deleted")
    remove_duplicates(target_dir, dry_run=True)

    # Uncomment below to actually delete
    # response = input("\nProceed with deletion? (yes/no): ")
    # if response.lower() == 'yes':
    #     remove_duplicates(target_dir, dry_run=False)
