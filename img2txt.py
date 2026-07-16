#!/data/data/com.termux/files/usr/bin/env python

import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytesseract
from PIL import Image

os.environ['TESSDATA_PREFIX'] = str(Path.home() / '.local/share/tessdata_best')

def extract_text(image_path):
    try:
        text = pytesseract.image_to_string(image_path, lang='eng')
        output_path = image_path.with_suffix('.txt')
        output_path.write_text(text, encoding='utf-8')
        return f"✓ {image_path.name}"
    except Exception as e:
        return f"✗ {image_path.name}: {e}"

def process_images(paths=None):
    if not paths:
        paths = [Path.cwd()]
    else:
        paths = [Path(p) for p in paths]
    
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
    image_files = []
    
    for path in paths:
        if path.is_file() and path.suffix.lower() in image_extensions:
            image_files.append(path)
        elif path.is_dir():
            image_files.extend(path.rglob('*'))
    
    image_files = [f for f in image_files if f.is_file() and f.suffix.lower() in image_extensions]
    
    if not image_files:
        print("No image files found.")
        return
    
    print(f"Processing {len(image_files)} image(s)...\n")
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(extract_text, img): img for img in image_files}
        for future in as_completed(futures):
            print(future.result())

if __name__ == '__main__':
    process_images(sys.argv[1:] if len(sys.argv) > 1 else None)
