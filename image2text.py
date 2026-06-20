#!/data/data/com.termux/files/usr/bin/python

import sys
from collections import deque
from multiprocessing import get_context
from pathlib import Path

import cv2
from dh import fsz, get_files, gsz
from PIL import Image
from PIL.Image import Image

MAX_QUEUE = 16


def process_file(image_path: Path) -> Image:
    path = Path(path)
    img = cv2.imread(str(image_path))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    gaussian_blur = cv2.GaussianBlur(blurred, (0, 0), 3)
    sharpened = cv2.addWeighted(blurred, 1.5, gaussian_blur, -0.5, 0)
    binary = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    enhanced_img_pil = Image.fromarray(binary)
    enhanced = image_path.with_stem(image_path.stem + "_enhanced_pil")
    cv2.imwrite(str(enhanced), enhanced_img_pil)
    return enhanced_img_pil


def process_file2(image_path):
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"Error: Could not load image from {image_path}")
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    gaussian_blur = cv2.GaussianBlur(blurred, (0, 0), 3)
    sharpened = cv2.addWeighted(blurred, 1.5, gaussian_blur, -0.5, 0)
    binary = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    enhanced = image_path.with_stem(image_path.stem + "_enhanced_cv")
    cv2.imwrite(str(enhanced), binary)
    return binary


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".png", ".jpg"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    with get_context("spawn").Pool(8) as pool:
        pending = deque()
        for f in files:
            pending.append(pool.apply_async(process_file, (f,)))
            if len(pending) > MAX_QUEUE:
                pending.popleft().get()
        while pending:
            pending.popleft().get()
    with get_context("spawn").Pool(8) as pool:
        pending = deque()
        for f in files:
            pending.append(pool.apply_async(process_file2, (f,)))
            if len(pending) > MAX_QUEUE:
                pending.popleft().get()
        while pending:
            pending.popleft().get()
    diff_size = before - gsz(cwd)
    print(f"space saved : {fsz(diff_size)}")


if __name__ == "__main__":
    main()
