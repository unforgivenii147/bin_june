#!/data/data/com.termux/files/usr/bin/env python

"""Module for move_tests_dirs.py."""

from __future__ import annotations

import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Tuple

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def move_tests_folder(tests_path: Path, base_src: Path, base_dst: Path) -> Tuple[bool, str]:
    try:
        relative_path = tests_path.relative_to(base_src)
        parent_relative = relative_path.parent
        dst_path = base_dst / parent_relative / tests_path.name
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tests_path), str(dst_path))
        return True, f"Moved: {tests_path} -> {dst_path}"
    except Exception as e:
        return False, f"Error moving {tests_path}: {e}"


def move_tests_recursive(source_dir: str = ".", max_workers: int = 4) -> int:
    source = Path(source_dir).resolve()
    destination = Path.home() / "tmp" / "test"
    tests_folders = list(source.rglob("tests"))
    tests_folders = [p for p in tests_folders if p.is_dir()]
    if not tests_folders:
        print("No 'tests' folders found.")
        return 0
    print(f"Found {len(tests_folders)} 'tests' folder(s) to move")
    print(f"Source: {source}")
    print(f"Destination: {destination}")
    print()
    destination.parent.mkdir(parents=True, exist_ok=True)
    moved_count = 0
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(move_tests_folder, tests_path, source, destination): tests_path
            for tests_path in tests_folders
        }
        for future in as_completed(futures):
            success, message = future.result()
            print(message)
            if success:
                moved_count += 1
    print()
    print(f"✓ Successfully moved {moved_count}/{len(tests_folders)} directories")
    return moved_count


if __name__ == "__main__":
    move_tests_recursive()
