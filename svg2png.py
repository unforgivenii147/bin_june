#!/data/data/com.termux/files/usr/bin/python

from io import BytesIO
from pathlib import Path

import cairosvg
from dh import get_files
from pbar import Pbar
from PIL import Image


def process_file(fp):
    png_file = fp.with_suffix(".png")
    with fp.open("rb") as image:
        imageBinary = BytesIO(image.read())
        buff = BytesIO()
        cairosvg.svg2png(bytestring=imageBinary.getvalue(), write_to=buff)
        buff.seek(0)
        img = Image.open(buff)
        img.save(png_file)


def main():
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".svg"])
    with Pbar("...") as pbar:
        for f in pbar.wrap(files):
            process_file(f)


if __name__ == "__main__":
    main()
