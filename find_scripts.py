#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
from pathlib import Path
from dh import should_skip, is_binary, getfiles, is_python_file

CHUNK_SIZE = 1024 * 1024


def get_filez(root_dir: str | Path):

    visited_dirs: set[Path] = set()
    root_dir = Path(root_dir)
    if root_dir.is_dir():
        for dirpath, dirnames, filenames in root_dir.walk():
            base_path = Path(dirpath)
            for dirname in list(dirnames):
                full_path = base_path / dirname
                resolved_path = full_path.resolve()
                if should_skip(full_path) or resolved_path in visited_dirs:
                    dirnames.remove(dirname)
                visited_dirs.add(resolved_path)
            for filename in filenames:
                filepath = base_path / filename
                if not should_skip(filepath):
                    yield filepath
    else:
        yield root_dir


def find_scripts_without_extension(directory: Path):
    swe = []
    for item in get_filez(directory):
        if should_skip(item):
            continue
        if item.is_file() and (not item.suffix):
            if is_binary(item):
                continue
            if is_python_file(item):
                swe.append(item)
    return swe


if __name__ == "__main__":
    cwd = Path.cwd()
    found_scripts = find_scripts_without_extension(cwd)
    if found_scripts:
        print("Found Python scripts without extension (relative paths):")
        for script_path in found_scripts:
            print(script_path.relative_to(cwd))
    else:
        print("No Python scripts without extension found in the current directory or its subdirectories.")
