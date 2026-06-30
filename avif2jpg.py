#!/data/data/com.termux/files/usr/bin/python

import os
from pathlib import Path
from PIL import Image

input_dir = "avif_images"
output_dir = "jpg_images"
Path(output_dir).mkdir(exist_ok=True, parents=True)
for filename in os.listdir(input_dir):
    if filename.lower().endswith((".avif", ".aviff")):
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, os.path.splitext(filename)[0] + ".jpg")
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.save(output_path, "JPEG", quality=95)
