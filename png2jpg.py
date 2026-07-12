#!/data/data/com.termux/files/usr/bin/env python
import sys
from pathlib import Path

from PIL import Image

if len(sys.argv) != 2:
    print("Usage: python convert_png_to_jpg.py <filename.png>")
    sys.exit(1)
fname = Path(sys.argv[1])
if not fname.is_file():
    print(f"File {fname} does not exist.")
    sys.exit(1)
if fname.suffix.lower() != ".png":
    print("File must be a PNG.")
    sys.exit(1)
img = Image.open(fname).convert("RGB")
jpg_fname = fname.with_suffix(".jpg")
img.save(jpg_fname, "JPEG")
fname.unlink()
print(f"Converted {fname} to {jpg_fname} and deleted the original PNG.")
