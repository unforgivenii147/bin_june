#!/data/data/com.termux/files/usr/bin/python

import sys
from collections import deque
from multiprocessing import Pool
from pathlib import Path

import cv2 as cv
from dh import get_files

cwd = Path.cwd()


def process_file(fp):
    img = cv.imread(str(fp))
    if img is None:
        return
    img = 255 - img
    cv.imwrite(str(fp), img)
    print(f"{fp.relative_to(cwd)} updated.")


def main():
    args = sys.argv[1:]
    files = [Path(arg) for arg in args] if args else get_files(cwd, ext=[".png", ".jpg"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    with Pool(8) as pool:
        pending = deque()
        for f in files:
            pending.append(pool.apply_async(process_file, (f,)))
            if len(pending) > 16:
                pending.popleft().get()
        while pending:
            pending.popleft().get()
    print("done.")


if __name__ == "__main__":
    sys.exit(main())
