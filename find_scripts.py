#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

from pathlib import Path

from dh import get_filez, is_binary, should_skip

CHUNK_SIZE = 1024 * 1024

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def find_scripts_without_extension(directory: Path):
    scripts_without_extension = []
    for item in get_filez(directory):
        if item.is_symlink():
            continue
        if ".git" in item.parts:
            continue
        if item.is_file() and not item.suffix:
            if is_binary(item):
                continue
            try:
                with item.open("r", encoding="utf-8") as f:
                    first_line = f.readline()
                    if first_line.strip().startswith("#!"):
                        scripts_without_extension.append(item)
            except Exception as e:
                print(f"Could not read {item}: {e}")
    return scripts_without_extension


if __name__ == "__main__":
    cwd = Path.cwd()
    found_scripts = find_scripts_without_extension(cwd)
    if found_scripts:
        print("Found Python scripts without extension (relative paths):")
        for script_path in found_scripts:
            print(script_path.relative_to(cwd))
    else:
        print("No Python scripts without extension found in the current directory or its subdirectories.")
