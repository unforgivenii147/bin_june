#!/data/data/com.termux/files/usr/bin/env python


"""
QR Code Extractor using zbar (Lightweight)
Install: pip install pyzbar pillow
"""

from __future__ import annotations

import os
import sys

import pyzbar.pyzbar as pyzbar
from PIL import Image

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def extract_qr_data_zbar(image_path):
    try:
        with Image.open(image_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            decoded = pyzbar.decode(img)
            results = []
            for obj in decoded:
                if obj.type == "QRCODE":
                    results.append(obj.data.decode("utf-8"))
            return results
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return []


def main():
    if len(sys.argv) != 2:
        print("Usage: python qr_extractor.py <path_to_qrcode_image>")
        sys.exit(1)
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Error: File '{image_path}' not found.")
        sys.exit(1)
    results = extract_qr_data_zbar(image_path)
    if results:
        print(f"\nFound {len(results)} QR code(s):")
        print("-" * 50)
        for i, data in enumerate(results, 1):
            print(f"QR #{i}: {data}")
        print("-" * 50)
    else:
        print("No QR codes found in the image.")


if __name__ == "__main__":
    main()
