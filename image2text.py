#!/data/data/com.termux/files/usr/bin/env python

"""Module for image2text.py."""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
from dh import mpf3
from PIL import Image
from PIL.Image import Image

# Try to import OpenCV, fallback to skimage if not available
try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    try:
        from skimage import io, color, filters, util
        from skimage.util import img_as_ubyte

        HAS_SKIMAGE = True
    except ImportError:
        print("Error: Neither OpenCV nor scikit-image is available.")
        print("Install one of them: pip install opencv-python or pip install scikit-image")
        sys.exit(1)


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = ("B", "KB", "MB", "GB", "TB")
    if sz == 0:
        return "0 B"
    i = min((int(sz).bit_length() - 1) // 10, len(units) - 1)
    value = sz / 1024**i
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


MAX_QUEUE = 16


def process_image_cv2(image_path: Path) -> Image:
    """Process image using OpenCV"""
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"Error: Could not load image from {image_path}")
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    gaussian_blur = cv2.GaussianBlur(blurred, (0, 0), 3)
    sharpened = cv2.addWeighted(blurred, 1.5, gaussian_blur, -0.5, 0)
    binary = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    enhanced_img_pil = Image.fromarray(binary)
    enhanced = image_path.with_stem(image_path.stem + "_enhanced_pil")
    cv2.imwrite(str(enhanced), binary)

    return enhanced_img_pil


def process_image_skimage(image_path: Path) -> Image:
    """Process image using scikit-image"""
    try:
        img = io.imread(str(image_path))
    except Exception as e:
        print(f"Error: Could not load image from {image_path}: {e}")
        return None

    # Convert to grayscale if image is RGB
    if len(img.shape) == 3:
        gray = color.rgb2gray(img)
    else:
        gray = img

    # Apply Gaussian blur (sigma=5 approximates the (5,5) kernel in OpenCV)
    blurred = filters.gaussian(gray, sigma=5 / 3)  # kernel_size/3 ≈ sigma

    # Second blur for the sharpening effect
    gaussian_blur = filters.gaussian(blurred, sigma=3 / 3)

    # Sharpening: original + 1.5 * (original - blurred) = 1.5*original - 0.5*blurred
    sharpened = 1.5 * blurred - 0.5 * gaussian_blur
    sharpened = np.clip(sharpened, 0, 1)

    # Adaptive threshold approximation using local thresholding
    from skimage.filters import threshold_local

    binary = sharpened > threshold_local(sharpened, 11, "gaussian")

    # Convert to uint8
    binary_uint8 = img_as_ubyte(binary)

    enhanced_img_pil = Image.fromarray(binary_uint8)
    enhanced = image_path.with_stem(image_path.stem + "_enhanced_pil")

    io.imsave(str(enhanced), binary_uint8)

    return enhanced_img_pil


def process_file(image_path: Path) -> Image:
    """Main processing function that selects the appropriate backend"""
    if HAS_CV2:
        return process_image_cv2(image_path)
    else:

        return process_image_skimage(image_path)


def process_file2(image_path):
    """Alternative processing with slightly different parameters"""
    if HAS_CV2:
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
    else:
        # skimage fallback with slightly different parameters
        import numpy as np

        try:
            img = io.imread(str(image_path))
        except Exception as e:
            print(f"Error: Could not load image from {image_path}: {e}")
            return None

        if len(img.shape) == 3:
            gray = color.rgb2gray(img)
        else:
            gray = img

        blurred = filters.gaussian(gray, sigma=5 / 3)
        gaussian_blur = filters.gaussian(blurred, sigma=1.0)
        sharpened = 1.5 * blurred - 0.5 * gaussian_blur
        sharpened = np.clip(sharpened, 0, 1)

        from skimage.filters import threshold_local

        binary = sharpened > threshold_local(sharpened, 11, "gaussian")
        binary_uint8 = img_as_ubyte(binary)

        enhanced = image_path.with_stem(image_path.stem + "_enhanced_cv")
        io.imsave(str(enhanced), binary_uint8)

        return binary_uint8


def main() -> None:
    print(f"Using {'OpenCV' if HAS_CV2 else 'scikit-image'} for image processing")

    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".png", ".jpg"])

    if not files:
        print("No image files found to process")
        sys.exit(0)

    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)

    mpf3(process_file, files)
    mpf3(process_file2, files)

    diff_size = before - gsz(cwd)
    print(f"space saved : {fsz(diff_size)}")


if __name__ == "__main__":
    main()
