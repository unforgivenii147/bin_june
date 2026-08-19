#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

SOURCE_DIR = Path.home() / ".local" / "lib" / "python3.12" / "site-packages"
EXCLUDED = [
    "numpy",
    "scipy",
    "pandas",
]


def move_tests_folder(tests_path: Path, base_src: Path, base_dst: Path, dry_run: bool = False) -> tuple[bool, str]:
    try:
        relative_path = tests_path.relative_to(base_src).resolve()
        parent_relative = relative_path.parent
        dst_path = base_dst / parent_relative / tests_path.name
        dst_path = dst_path.resolve()
        if dry_run:
            return True, f"[DRY RUN] Would move: {tests_path} -> {dst_path}"

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tests_path), str(dst_path))
        return True, f"Moved: {tests_path} -> {dst_path}"
    except Exception as e:
        return False, f"Error moving {tests_path}: {e}"


def move_tests_recursive(source_dir: str = SOURCE_DIR, dry_run: bool = False) -> int:
    source = Path(source_dir).resolve()
    destination = Path.home() / "tmp" / "test_dirs"
    tests_folders = list(source.rglob("tests"))
    tests_folders = [p for p in tests_folders if p.is_dir() and not (g in p.parts for g in EXCLUDED)]
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
            executor.submit(move_tests_folder, tests_path, source, destination, dryrun=dry_run): tests_path
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
    import sys

    DRY_RUN = "-d" in sys.argv
    move_tests_recursive(DRY_RUN)
