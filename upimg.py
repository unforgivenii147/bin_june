#!/data/data/com.termux/files/usr/bin/python
import cv2
import sys
from pathlib import Path
from dh import get_files, mpf3


def process_file(path):
    path = Path(path)
    img = cv2.imread(path)
    # denoised = cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 3, 14)
    h, w = img.shape[:2]
    if h > 2000 or w > 2000:
        return
    print(f"[\u2713] {path.name}:{h}x{w}")

    # nearest = cv2.resize(img, (w*2, h*2), interpolation=cv2.INTER_NEAREST)
    bilinear = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_LINEAR)
    bicubic = cv2.resize(bilinear, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    lanczos = cv2.resize(bicubic, (w * 4, h * 4), interpolation=cv2.INTER_LANCZOS4)
    # blurred = cv2.GaussianBlur(lanczos, (0,0), 3)
    sharpened = cv2.addWeighted(lanczos, 1.5, lanczos, -0.5, 0)
    cv2.imwrite(path, sharpened)


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".webp", ".jpg", ".jpeg", ".png"])
    mpf3(process_file, files)
