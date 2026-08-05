#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

from dh import get_files
from dh.jobutils import mpf3
from PIL import Image
from pytesseract import image_to_string


def extract_text(image_path: Path) -> str:
    """Extract text with explicit resource cleanup."""
    try:
        with Image.open(image_path) as img:
            if img.mode not in ("L", "RGB"):
                img = img.convert("RGB")

            result = image_to_string(img, lang="eng", config="--oem 1 --psm 6")

        print("*" * 40)
        print(result.strip() or "[No text detected]")
        return result.strip()

    except Exception as e:
        print(f"Error processing {image_path.name}: {e}")
        return ""


def process_file(path: Path) -> None:
    """Process single file with minimal memory footprint."""
    path = Path(path)
    txtfile = path.with_suffix(".txt")

    if txtfile.exists():
        print(f"✓ {path.name} already processed")
        return

    print(f"→ Processing {path.name}")
    text = extract_text(path)

    if text and len(text) > 5:
        try:
            txtfile.write_text(text, encoding="utf-8")
            print(f"✓ Saved {txtfile.name}")
        except Exception as e:
            print(f"✗ Failed to write {txtfile.name}: {e}")
    else:
        print(f"⚠ No significant text in {path.name}")


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]

    if args:
        files = [Path(p) for p in args if Path(p).is_file()]
    else:
        print("Scanning directory for images...")
        files = get_files(cwd, ext=[".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".webp"])

    if not files:
        print("No image files found.")
        return

    print(f"Found {len(files)} image(s). Starting OCR...\n")

    max_workers = 2

    if len(files) == 1:
        process_file(files[0])
    else:
        print(f"Using {max_workers} worker(s) for memory safety...")
        mpf3(process_file, files)


if __name__ == "__main__":
    main()
