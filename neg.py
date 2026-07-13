#!/data/data/com.termux/files/usr/bin/env python
"""
Convert all images in a directory (and subdirectories) to negative/inverted colors.
Processes images in parallel using multiprocessing.
"""

import argparse
import logging
import sys
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path

from PIL import Image

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Supported image extensions
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}


def is_image_file(file_path: Path) -> bool:
    """Check if the file is a supported image based on its extension."""
    return file_path.suffix.lower() in SUPPORTED_EXTENSIONS


def invert_image(image_path: Path, dry_run: bool = False) -> tuple[Path, bool]:
    """
    Invert (negative) a single image file in place.

    Args:
        image_path: Path to the image file
        dry_run: If True, only log what would be done without actually processing

    Returns:
        Tuple of (image_path, success_flag)
    """
    try:
        if dry_run:
            logger.info(f"[DRY RUN] Would invert: {image_path}")
            return (image_path, True)

        # Open and invert the image
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for consistency)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Invert the image
            inverted = img.point(lambda p: 255 - p)

            # Save in place (overwrite original)
            inverted.save(image_path, quality=95, optimize=True)

        logger.info(f"✓ Inverted: {image_path}")
        return (image_path, True)

    except Exception as e:
        logger.error(f"✗ Failed to process {image_path}: {e}")
        return (image_path, False)


def find_images(root_dir: Path, recursive: bool = True) -> list[Path]:
    """
    Find all image files in a directory.

    Args:
        root_dir: Root directory to search
        recursive: If True, search subdirectories recursively

    Returns:
        List of image file paths
    """
    if recursive:
        image_files = [f for f in root_dir.rglob("*") if f.is_file() and is_image_file(f)]
    else:
        image_files = [f for f in root_dir.iterdir() if f.is_file() and is_image_file(f)]

    return sorted(image_files)


def main():
    parser = argparse.ArgumentParser(
        description="Convert images to negative (invert colors) recursively in place",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./photos                 # Invert all images recursively in ./photos
  %(prog)s ./images -n 4            # Use 4 parallel processes
  %(prog)s ./images --dry-run       # Preview what would be processed
  %(prog)s ./images --no-recursive  # Only process current directory
        """,
    )

    parser.add_argument("directory", type=str, help="Directory containing images to invert")

    parser.add_argument(
        "-n", "--processes", type=int, default=None, help="Number of parallel processes (default: CPU count)"
    )

    parser.add_argument("--no-recursive", action="store_true", help="Do not process subdirectories recursively")

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be processed without actually modifying files"
    )

    parser.add_argument(
        "--extensions", type=str, nargs="+", help="Additional file extensions to process (e.g., .jpg .png)"
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate directory
    root_dir = Path(args.directory)
    if not root_dir.exists():
        logger.error(f"Directory does not exist: {root_dir}")
        sys.exit(1)

    if not root_dir.is_dir():
        logger.error(f"Path is not a directory: {root_dir}")
        sys.exit(1)

    # Add additional extensions if provided
    if args.extensions:
        for ext in args.extensions:
            if not ext.startswith("."):
                ext = "." + ext
            SUPPORTED_EXTENSIONS.add(ext.lower())

    # Find image files
    recursive = not args.no_recursive
    logger.info(f"Scanning {'recursively' if recursive else 'non-recursively'} in: {root_dir}")
    image_files = find_images(root_dir, recursive)

    if not image_files:
        logger.warning("No image files found to process")
        sys.exit(0)

    logger.info(f"Found {len(image_files)} image(s) to process")

    # Process images in parallel
    num_processes = args.processes or cpu_count()
    logger.info(f"Using {num_processes} process(es)")

    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be modified")

    # Create partial function with dry_run parameter
    invert_func = partial(invert_image, dry_run=args.dry_run)

    # Process using multiprocessing Pool
    with Pool(processes=num_processes) as pool:
        results = pool.map(invert_func, image_files)

    # Report results
    successful = sum(1 for _, success in results if success)
    failed = len(results) - successful

    logger.info(f"\n{'=' * 50}")
    logger.info(f"Processing complete!")
    logger.info(f"✓ Successful: {successful}")
    if failed > 0:
        logger.warning(f"✗ Failed: {failed}")
    logger.info(f"Total processed: {len(results)}")


if __name__ == "__main__":
    main()
