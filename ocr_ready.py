#!/data/data/com.termux/files/usr/bin/env python

import multiprocessing
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pytesseract

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".webp"}
BASE_DIR = Path.cwd()

# Try importing cv2, fallback to PIL if not available
try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    import io

    from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def deskew(image):
    """Deskew image using cv2 or PIL fallback"""
    if HAS_CV2:
        coords = np.column_stack(np.where(image > 0))
        if coords.size == 0:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        h, w = image.shape[:2]
        center = w // 2, h // 2
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    else:
        return image


def preprocess_image_cv2(img_path: Path):
    """Preprocess image using OpenCV"""
    img = cv2.imread(str(img_path))
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2)
    kernel = np.ones((1, 1), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    return deskew(cleaned)


def preprocess_image_pillow(img_path: Path):
    """Preprocess image using Pillow"""
    try:
        img = Image.open(str(img_path))
        if img.mode != "L":
            img = img.convert("L")

        w, h = img.size
        img = img.resize((w * 2, h * 2), Image.Resampling.BICUBIC)
        img = img.filter(ImageFilter.MedianFilter(size=3))

        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        img = img.point(lambda p: 255 if p > 128 else 0)
        img = img.filter(ImageFilter.SHARPEN)
        return img
    except Exception as e:
        return None


def preprocess_image(img_path: Path):
    """Preprocess image using available library"""
    if HAS_CV2:
        return preprocess_image_cv2(img_path)
    else:
        return preprocess_image_pillow(img_path)


def should_skip(path: Path) -> bool:
    """Skip non-image files"""
    if path.suffix.lower() not in SUPPORTED_EXT:
        return True
    return False


def save_processed_image(img, img_path: Path):
    """Save processed image in-place (overwrite original)"""
    if HAS_CV2 and isinstance(img, np.ndarray):
        cv2.imwrite(str(img_path), img)
    elif not HAS_CV2 and img is not None:
        img.save(str(img_path))
    else:
        raise ValueError("Unsupported image format")


def process_single_image(image_path: Path) -> dict:
    """Process a single image - meant to be run in parallel"""
    result = {"path": str(image_path), "success": False, "error": None, "size_before": 0, "size_after": 0}

    try:
        # Get original size
        result["size_before"] = image_path.stat().st_size

        # Process image
        processed = preprocess_image(image_path)
        if processed is None:
            result["error"] = "Failed to process image"
            return result

        # Save processed image (overwrite original)
        save_processed_image(processed, image_path)

        # Generate OCR text file alongside the image
        txt_path = image_path.with_suffix(".txt")
        if HAS_CV2:
            text = pytesseract.image_to_string(processed, config="--oem 1 --psm 6")
        else:
            text = pytesseract.image_to_string(processed, config="--oem 1 --psm 6")
        txt_path.write_text(text, encoding="utf-8")

        result["size_after"] = image_path.stat().st_size
        result["success"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


def get_image_files():
    """Get all image files recursively"""
    image_files = []
    for path in BASE_DIR.rglob("*"):
        if should_skip(path):
            continue
        image_files.append(path)
    return image_files


def process() -> None:
    """Process all images recursively in-place with parallel processing"""

    if not HAS_CV2:
        print("⚠️ OpenCV not found, using Pillow as fallback (limited functionality)")

    # Get all image files
    image_files = get_image_files()
    total_images = len(image_files)

    if total_images == 0:
        print("No images found to process.")
        return

    print(f"📊 Found {total_images} images to process")
    print(f"⚡ Using {multiprocessing.cpu_count()} CPU cores for parallel processing")
    print("🔄 Processing images in-place...\n")

    processed_count = 0
    error_count = 0
    total_before = 0
    total_after = 0

    # Use ProcessPoolExecutor for parallel processing
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        # Submit all tasks
        future_to_path = {executor.submit(process_single_image, path): path for path in image_files}

        # Process results as they complete
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()

                if result["success"]:
                    processed_count += 1
                    total_before += result["size_before"]
                    total_after += result["size_after"]
                    status = "✅"
                else:
                    error_count += 1
                    status = "❌"

                # Print progress
                relative = path.relative_to(BASE_DIR)
                print(f"{status} [{processed_count + error_count}/{total_images}] {relative}")

                if result.get("error"):
                    print(f"   ⚠️ Error: {result['error']}")

            except Exception as e:
                error_count += 1
                print(f"❌ [{processed_count + error_count}/{total_images}] {path.name}: {e}")

    # Summary
    print("\n" + "=" * 60)
    print(f"📊 Processing Summary:")
    print(f"   ✅ Successfully processed: {processed_count} images")
    print(f"   ❌ Errors: {error_count} images")
    print(f"   📁 Total images: {total_images}")

    if processed_count > 0:
        size_reduction = ((total_before - total_after) / total_before * 100) if total_before > 0 else 0
        print(f"   📦 Total size before: {total_before / (1024 * 1024):.2f} MB")
        print(f"   📦 Total size after: {total_after / (1024 * 1024):.2f} MB")
        print(f"   📉 Size reduction: {size_reduction:.1f}%")

    print("=" * 60)


if __name__ == "__main__":
    print("⚠️  WARNING: This script will MODIFY original image files in-place!")
    print("⚠️  NO BACKUPS will be created.")
    print("⚠️  CTRL+C to cancel, ENTER to continue...")

    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user.")
        sys.exit(0)

    process()
