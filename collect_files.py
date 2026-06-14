#!/data/data/com.termux/files/usr/bin/python

import shutil
import sys
from pathlib import Path


def unique_destination_path(dest_dir: Path, filename: str) -> Path:
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def collect_files_by_extension(extension: str) -> None:
    cwd = Path.cwd()
    target_dir = cwd / extension
    target_dir.mkdir(parents=True, exist_ok=True)
    copied_count = 0
    for file_path in cwd.rglob(f"*.{extension}"):
        if file_path.is_file() and target_dir not in file_path.parents:
            try:
                destination_path = unique_destination_path(target_dir, file_path.name)
                shutil.copy2(file_path, destination_path)
                print(f"Copied: {file_path} -> {destination_path}")
                copied_count += 1
            except Exception as e:
                print(f"Error copying {file_path}: {e}")
    print("\nFinished collecting files.")
    print(f"Total files copied: {copied_count}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python collect_files.py <extension>")
        sys.exit(1)
    file_extension = sys.argv[1].lower().strip(".")
    collect_files_by_extension(file_extension)
