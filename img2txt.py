#!/data/data/com.termux/files/usr/bin/python

import sys
from multiprocessing import get_context
from pathlib import Path

from dh import get_files
from PIL import Image
from pytesseract import image_to_string


def extract_text(image_path):
    img = Image.open(image_path)
    return image_to_string(img, lang="eng", config="--oem 1 --psm 6")


def process_file(path):
    print(f"Processing {path.name}")
    path = Path(path)
    text = extract_text(path)
    if text and len(text) > 1:
        txtfile = path.with_suffix(".txt")
        txtfile.write_text(text, encoding="utf-8")
        print(f"{txtfile} created.")
    else:
        print("No text found.")


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".jpg", ".png"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    p = get_context("spawn").Pool(4)
    for _ in p.imap_unordered(process_file, files):
        pass
    p.close()
    p.join()


if __name__ == "__main__":
    main()
