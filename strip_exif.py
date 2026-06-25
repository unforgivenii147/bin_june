#!/data/data/com.termux/files/usr/bin/python
"""
Strip EXIF data from image files using pathlib only.
Supports parallel processing, size reporting, and file/directory input.
"""

import argparse
import io
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path

from PIL import Image


def get_file_size(file_path):
    """Get file size in bytes using pathlib."""
    return file_path.stat().st_size


def get_folder_size(folder_path):
    """Calculate total size of all files in a folder recursively."""
    total = 0
    for item in folder_path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def format_size(size_bytes):
    """Format bytes to human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def strip_exif_single(image_path, backup=False, verbose=False):
    """
    Strip EXIF data from a single image file.

    Args:
        image_path: Path object pointing to the image file
        backup: If True, create a backup of the original file
        verbose: If True, print detailed output

    Returns:
        dict: Result with status, original_size, new_size, and message
    """
    result = {
        "path": image_path,
        "success": False,
        "original_size": 0,
        "new_size": 0,
        "message": "",
        "backup_created": False,
    }

    try:
        # Get original size
        original_size = image_path.stat().st_size
        result["original_size"] = original_size

        # Read the image
        with Image.open(image_path) as img:
            # Create backup if requested
            if backup:
                backup_path = image_path.with_suffix(image_path.suffix + ".backup")
                # Copy using pathlib
                backup_path.write_bytes(image_path.read_bytes())
                result["backup_created"] = True
                if verbose:
                    print(f"  📋 Backup: {backup_path.name}")

            # Get image data without EXIF
            # Save to memory first to avoid overwriting original on error
            img_without_exif = Image.new(img.mode, img.size)
            img_without_exif.putdata(list(img.getdata()))

            # Save to memory buffer first
            buffer = io.BytesIO()
            format_kwargs = {"format": img.format}
            if img.format == "JPEG":
                format_kwargs["quality"] = 95
                format_kwargs["optimize"] = True
            elif img.format == "PNG":
                format_kwargs["optimize"] = True

            # For JPEG, we need to strip EXIF by saving without exif parameter
            if img.format == "JPEG":
                img_without_exif.save(buffer, format=img.format, quality=95, optimize=True, exif=None)
            else:
                # For other formats, just save normally (they may not have EXIF)
                # or use exif=None for formats that support it
                try:
                    img_without_exif.save(buffer, **format_kwargs, exif=None)
                except TypeError:
                    # Some formats don't support exif parameter
                    img_without_exif.save(buffer, **format_kwargs)

            # Get new size from buffer
            new_size = buffer.tell()
            result["new_size"] = new_size

            # Only save if size is smaller (or we don't care about size)
            if new_size < original_size or True:  # Always save to strip EXIF
                # Write the buffer content to the original file
                buffer.seek(0)
                image_path.write_bytes(buffer.getvalue())
                result["success"] = True

                size_change = new_size - original_size
                percent_change = (size_change / original_size) * 100

                if verbose:
                    print(f"  ✅ {image_path.name}")
                    print(f"     {format_size(original_size)} → {format_size(new_size)} ({percent_change:+.1f}%)")

                result["message"] = f"Stripped EXIF: {size_change:+.0f}B ({percent_change:+.1f}%)"
            else:
                result["message"] = "No size reduction, skipped"

    except Exception as e:
        result["success"] = False
        result["message"] = f"Error: {str(e)}"
        if verbose:
            print(f"  ❌ {image_path.name}: {str(e)}")

    return result


def process_image_file(image_path, backup=False, verbose=False):
    """Wrapper for process_pool to handle path conversion."""
    return strip_exif_single(image_path, backup, verbose)


def find_image_files(paths, extensions, recursive=True):
    """Find all image files from a list of paths."""
    image_files = []
    extensions = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]
    extensions_lower = [ext.lower() for ext in extensions]
    extensions_upper = [ext.upper() for ext in extensions]
    all_extensions = set(extensions_lower + extensions_upper)

    for path_str in paths:
        path = Path(path_str)

        if not path.exists():
            print(f"⚠️  Path does not exist: {path}")
            continue

        if path.is_file():
            # Check if file has matching extension
            if path.suffix.lower() in all_extensions:
                image_files.append(path)
            elif not extensions:  # If no extensions specified, include all files
                image_files.append(path)

        elif path.is_dir():
            # Directory - find files recursively
            if recursive:
                for ext in all_extensions:
                    # Use glob pattern for each extension
                    pattern = f"**/*{ext}"
                    image_files.extend(path.glob(pattern))
            else:
                # Non-recursive: only current directory
                for ext in all_extensions:
                    pattern = f"*{ext}"
                    image_files.extend(path.glob(pattern))
        else:
            print(f"⚠️  Unknown path type: {path}")

    # Remove duplicates and sort
    return sorted(set(image_files))


def main():
    parser = argparse.ArgumentParser(
        description="Strip EXIF data from image files with parallel processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                         # Process all images in current directory recursively
  %(prog)s image1.jpg image2.png   # Process specific files
  %(prog)s /path/to/images         # Process a directory
  %(prog)s file.jpg -b             # Process with backup
  %(prog)s . -j 4                  # Process with 4 parallel workers
  %(prog)s . --no-recursive        # Process current directory only (no subdirs)
        """,
    )

    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to process (default: current directory)",
    )

    parser.add_argument(
        "-b",
        "--backup",
        action="store_true",
        help="Create backup files (.backup) before stripping EXIF",
    )

    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        help=f"Number of parallel workers (default: CPU count = {cpu_count()})",
    )

    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not process subdirectories recursively",
    )

    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"],
        help="File extensions to process (default: .jpg .jpeg .png .tiff .tif .bmp .webp)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed output for each file",
    )

    parser.add_argument("--no-size-report", action="store_true", help="Skip folder size change report")

    args = parser.parse_args()

    # Determine number of workers
    if args.jobs is None:
        max_workers = min(cpu_count(), 4)  # Cap at 4 to avoid overloading
    else:
        max_workers = max(1, args.jobs)

    # Find all image files
    recursive = not args.no_recursive
    image_files = find_image_files(args.paths, args.extensions, recursive)

    if not image_files:
        print("ℹ️  No image files found.")
        return

    # Calculate initial folder size if multiple files in directories
    if not args.no_size_report:
        # Get unique parent directories
        dirs = set()
        for img in image_files:
            dirs.add(img.parent)

        initial_sizes = {}
        for dir_path in dirs:
            initial_sizes[dir_path] = get_folder_size(dir_path)

    print(f"📸 Found {len(image_files)} image file(s)")
    print(f"🔧 Using {max_workers} parallel worker(s)")
    print(f"💾 Backup: {'Yes' if args.backup else 'No'}")
    print(f"📁 Recursive: {'Yes' if recursive else 'No'}")
    print("-" * 60)

    # Process files in parallel
    results = []
    processed = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(process_image_file, img, args.backup, args.verbose): img for img in image_files
        }

        # Process results as they complete
        for future in as_completed(future_to_file):
            processed += 1
            img = future_to_file[future]

            try:
                result = future.result()
                results.append(result)

                if not args.verbose and not result["success"]:
                    print(f"❌ {img.name}: {result['message']}")
                elif not args.verbose and result["success"]:
                    # Show progress with minimal output
                    progress = f"[{processed}/{len(image_files)}]"
                    size_change = result["new_size"] - result["original_size"]
                    print(f"  {progress} {'✅' if result['success'] else '❌'} {img.name}")

            except Exception as e:
                print(f"❌ {img.name}: Unexpected error: {str(e)}")
                results.append({
                    "path": img,
                    "success": False,
                    "original_size": 0,
                    "new_size": 0,
                    "message": f"Unexpected error: {str(e)}",
                    "backup_created": False,
                })

    # Report results
    print("-" * 60)

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    # Calculate total size change
    total_original = sum(r["original_size"] for r in results)
    total_new = sum(r["new_size"] for r in results)
    total_change = total_new - total_original

    print(f"\n📊 Summary:")
    print(f"   Total files: {len(results)}")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📦 Original size: {format_size(total_original)}")
    print(f"   📦 New size: {format_size(total_new)}")
    print(
        f"   💰 Change: {format_size(total_change)} ({total_change / total_original * 100:+.1f}% if total_original > 0 else 'N/A')"
    )

    # Folder size change report
    if not args.no_size_report and len(dirs) > 0:
        print(f"\n📁 Folder size changes:")
        for dir_path in sorted(dirs):
            final_size = get_folder_size(dir_path)
            initial_size = initial_sizes.get(dir_path, 0)
            change = final_size - initial_size
            if change != 0:
                percent = (change / initial_size * 100) if initial_size > 0 else 0
                print(f"   {dir_path}:")
                print(f"      {format_size(initial_size)} → {format_size(final_size)} ({percent:+.1f}%)")

    # Show backup files created
    backups = [r for r in results if r.get("backup_created", False)]
    if backups:
        print(f"\n💾 Backups created for {len(backups)} file(s)")
        if args.verbose:
            for r in backups[:5]:  # Show first 5
                backup_path = r["path"].with_suffix(r["path"].suffix + ".backup")
                print(f"   📋 {backup_path.name}")
            if len(backups) > 5:
                print(f"   ... and {len(backups) - 5} more")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
