#!/data/data/com.termux/files/usr/bin/python
import hashlib
import os
import pathlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import xxhash


def get_file_hash(filepath):
    """Calculate xxh64 hash of a file."""
    try:
        xxh = xxhash.xxh64()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                xxh.update(chunk)
        return filepath, xxh.hexdigest()
    except (OSError, PermissionError):
        return filepath, None


def remove_duplicates(root_dir):
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

    # 2. Hash files in parallel
    files_to_hash = [p for paths in potential_dups.values() for p in paths]
    hash_map = defaultdict(list)

    print(f"Hashing {len(files_to_hash)} potential duplicate files...")
    with ThreadPoolExecutor() as executor:
        for filepath, file_hash in executor.map(get_file_hash, files_to_hash):
            if file_hash:
                hash_map[file_hash].append(filepath)

    # 3. Identify duplicates and delete
    total_freed = 0
    for file_hash, paths in hash_map.items():
        if len(paths) > 1:
            # Sort by modification time (oldest first)
            paths.sort(key=lambda p: p.stat().st_mtime)

            # Keep index 0 (oldest), delete the rest
            to_delete = paths[1:]
            for p in to_delete:
                try:
                    file_size = p.stat().st_size
                    p.unlink()
                    total_freed += file_size
                    print(f"Deleted: {p}")
                except OSError as e:
                    print(f"Error deleting {p}: {e}")

    print(f"\nCleanup complete.")
    print(f"Total disk space freed: {total_freed / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    # Change '.' to the specific directory you want to clean
    target_dir = "."
    remove_duplicates(target_dir)
