#!/data/data/com.termux/files/usr/bin/env python
import os
import sys
from collections import defaultdict

from ppdeep import hash_from_file


from pathlib import Path
from os import scandir as os_scandir


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def find_dups(cwd: str):
    files_by_hash = defaultdict(list)
    duplicate_count = 0
    deleted_count = 0
    total_deleted_size = 0
    files = get_files(cwd)
    for path in files:
        if path.is_symlink():
            continue
        if path.is_file():
            try:
                file_hash = hash_from_file(str(path))
                files_by_hash[file_hash].append(path)
            except Exception as e:
                print(f"Error processing file {path}: {e}")
                continue
    for file_hash, paths in files_by_hash.items():
        if len(paths) > 1:
            duplicate_count += len(paths) - 1
            paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            for dup_found in paths:
                print(os.path.relpath(dup_found))
            for filetodel in paths[1:]:
                try:
                    get_size = filetodel.stat().st_size
                    deleted_count += 1
                    total_deleted_size += get_size
                except Exception as e:
                    print(f"Error deleting file {filetodel}: {e}")
        else:
            continue
    return duplicate_count, deleted_count, total_deleted_size


if __name__ == "__main__":
    root_folder = sys.argv[1].strip()
    find_dups(root_folder)
