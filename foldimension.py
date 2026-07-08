#!/data/data/com.termux/files/usr/bin/env python


"""
folderize_images.py
Recursively find all image files in the current directory,
group them by (width, height), and move them into folders
named after their resolution.
If a resolution group contains only a single image, that image
is moved into an "other" folder instead.
Uses pathlib for all filesystem operations.
"""

import shutil
from collections import defaultdict
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: This script requires Pillow. Install it with: pip install Pillow")
    exit(1)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".ico"}


def collect_images(root: Path):
    size_to_files = defaultdict(list)
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            with Image.open(file_path) as img:
                width, height = img.size
            size_to_files[width, height].append(file_path)
        except Exception as e:
            print(f"Warning: Skipping {file_path} - {e}")
    return size_to_files


def unique_destination(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1
    while True:
        new_dest = parent / f"{stem}_{counter}{suffix}"
        if not new_dest.exists():
            return new_dest
        counter += 1


def organize_images(root: Path, size_to_files: dict) -> None:
    for (width, height), files in size_to_files.items():
        if len(files) == 1:
            folder = "other"
        else:
            folder = f"{width}x{height}"
        folder_path = root / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        for src in files:
            dest = folder_path / src.name
            dest = unique_destination(dest)
            shutil.move(src, dest)
            print(f"Moved: {src} -> {dest}")


def main() -> None:
    root = Path.cwd()
    print(f"Scanning {root} for image files...")
    size_to_files = collect_images(root)
    total_files = sum(len(v) for v in size_to_files.values())
    if total_files == 0:
        print("No image files found.")
        return
    print(f"Found {total_files} image(s) in {len(size_to_files)} resolution group(s).")
    organize_images(root, size_to_files)
    print("Done.")


if __name__ == "__main__":
    main()
