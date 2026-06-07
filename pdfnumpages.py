#!/data/data/com.termux/files/usr/bin/python

import sys
from multiprocessing import get_context
from pathlib import Path

import pdfplumber
from fastwalk import walk_files


def process_file(fp):
    fp = Path(fp)
    if fp.exists() and (not fp.is_symlink()):
        with pdfplumber.open(fp) as pdf:
            numpages = len(pdf.pages)
            new_name = fp.stem + str(numpages) + ".pdf"
            print(new_name)
            np = Path(f"{fp.parent}/{new_name}")
            if str(numpages) in fp.stem:
                return
            if not np.exists():
                Path(fp).rename(np)
                print(f"{fp.name} --> {np.name}")
            else:
                print(f"{np.name} exists.")
    return


def main():
    files = []
    for pth in walk_files("."):
        path = Path(pth)
        if path.is_file() and path.suffix == ".pdf":
            files.append(path)
    with get_context("spawn").Pool(8) as pool:
        for _ in pool.imap_unordered(process_file, files):
            pass


if __name__ == "__main__":
    sys.exit(main())
