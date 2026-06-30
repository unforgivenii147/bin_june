#!/data/data/com.termux/files/usr/bin/python
"""
Compress or decompress folders using zstandard compression.
- Uses tar to archive folders first (no shutil for compression)
- Uses pathlib for path operations
- Uses multiprocessing for parallel operations
- Shows progress bar
- Removes original folders after successful compression
- Stores compressed files in current directory (not subdir)
- Skips specified directories
"""

import os
import sys
import tarfile
import argparse
import multiprocessing as mp
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import zstandard as zstd
from tqdm import tqdm
import shutil

# Directories to skip
SKIP_DIRS = {
    "zstandard",
    "0",
    "compressed",
    "faprint",
    "packaging",
    "joblib",
    "loguru",
    "setuptools",
    "pip",
    "wheel",
    ".git",
    "dist",
    "build",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
}


def get_folder_size(folder_path: Path) -> int:
    """Calculate total size of folder in bytes."""
    total_size = 0
    for file_path in folder_path.rglob("*"):
        if file_path.is_file():
            total_size += file_path.stat().st_size
    return total_size


def should_skip_folder(folder_path: Path) -> bool:
    """Check if folder should be skipped."""
    # Skip if folder name is in SKIP_DIRS
    if folder_path.name in SKIP_DIRS:
        return True

    # Skip if folder path contains any skip directory
    for part in folder_path.parts:
        if part in SKIP_DIRS:
            return True

    return False


def compress_folder(folder_path: Path, output_dir: Path, compression_level: int = 3, threads: int = 2) -> tuple:
    """
    Compress a single folder using zstandard.
    Returns (success, folder_name, compressed_size, original_size, error_msg)
    """
    try:
        folder_name = folder_path.name
        zst_path = output_dir / f"{folder_name}.tar.zst"
        temp_tar_path = output_dir / f"temp_{folder_name}.tar"

        # Get original size before compression
        original_size = get_folder_size(folder_path)

        # Create tar archive
        with tarfile.open(temp_tar_path, "w", dereference=True) as tar:
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    arcname = str(file_path.relative_to(folder_path.parent))
                    tar.add(str(file_path), arcname=arcname)

        # Compress with zstandard
        cctx = zstd.ZstdCompressor(level=compression_level, threads=threads)

        with open(temp_tar_path, "rb") as f_in:
            compressed_data = cctx.compress(f_in.read())

        with open(zst_path, "wb") as f_out:
            f_out.write(compressed_data)

        compressed_size = zst_path.stat().st_size

        # Clean up
        temp_tar_path.unlink()
        shutil.rmtree(folder_path)

        return (True, folder_name, compressed_size, original_size, None)

    except Exception as e:
        return (False, folder_path.name, 0, 0, str(e))


def decompress_file(zst_path: Path, output_dir: Path, threads: int = 2) -> tuple:
    """
    Decompress a single .tar.zst file.
    Returns (success, filename, extracted_size, error_msg)
    """
    try:
        # Read compressed file
        with open(zst_path, "rb") as f:
            compressed_data = f.read()

        # Decompress
        dctx = zstd.ZstdDecompressor()
        decompressed_data = dctx.decompress(compressed_data)

        # Get original filename (without .tar.zst)
        base_name = zst_path.stem.replace(".tar", "")
        tar_path = output_dir / f"temp_{base_name}.tar"

        # Write decompressed tar
        with open(tar_path, "wb") as f:
            f.write(decompressed_data)

        # Extract tar
        extract_dir = output_dir / base_name
        extract_dir.mkdir(exist_ok=True)

        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(path=extract_dir)

        # Get extracted size
        extracted_size = get_folder_size(extract_dir)

        # Clean up
        tar_path.unlink()

        # Remove compressed file
        zst_path.unlink()

        return (True, base_name, extracted_size, None)

    except Exception as e:
        return (False, zst_path.name, 0, str(e))


def process_folders_compress(
    root_dir: Path, min_size_mb: int = 5, compression_level: int = 3, threads: int = 2, max_workers: int = None
):
    """
    Find and compress folders > min_size_mb.
    """
    if max_workers is None:
        max_workers = mp.cpu_count()

    # Find all folders > min_size_mb
    folders_to_compress = []
    total_folders = 0
    skipped_folders = 0
    skipped_by_name = 0

    print(f"Scanning folders in {root_dir}...")
    print(f"Skipping directories: {', '.join(sorted(SKIP_DIRS))}")

    for item in root_dir.iterdir():
        if item.is_dir():
            total_folders += 1

            # Skip directories in SKIP_DIRS
            if should_skip_folder(item):
                skipped_by_name += 1
                print(f"  ⏭ Skipping: {item.name} (in skip list)")
                continue

            size_bytes = get_folder_size(item)
            size_mb = size_bytes / (1024 * 1024)

            if size_mb > min_size_mb:
                folders_to_compress.append((item, size_mb))
                print(f"  Found: {item.name} ({size_mb:.2f} MB)")
            else:
                skipped_folders += 1

    if not folders_to_compress:
        print(
            f"\nNo folders > {min_size_mb}MB found. Scanned {total_folders} folders, "
            f"skipped {skipped_folders} smaller folders, {skipped_by_name} by name."
        )
        return

    print(
        f"\nFound {len(folders_to_compress)} folders to compress "
        f"(skipped {skipped_folders} folders <= {min_size_mb}MB, "
        f"{skipped_by_name} by name)"
    )
    print(f"Using compression level {compression_level}, {threads} threads per worker")
    print(f"Using {max_workers} parallel workers")
    print(f"Compressed files will be saved to: {root_dir}\n")

    # Compress folders in parallel
    successful = 0
    failed = 0
    total_saved = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_folder = {
            executor.submit(
                compress_folder,
                folder_path,
                root_dir,  # Save to current directory, not subdir
                compression_level,
                threads,
            ): (folder_path, size_mb)
            for folder_path, size_mb in folders_to_compress
        }

        with tqdm(total=len(folders_to_compress), desc="Compressing", unit="folder") as pbar:
            for future in as_completed(future_to_folder):
                folder_path, size_mb = future_to_folder[future]
                try:
                    success, name, comp_size, orig_size, error = future.result()

                    if success:
                        successful += 1
                        saved = orig_size - comp_size
                        total_saved += saved
                        compression_ratio = (comp_size / orig_size) * 100 if orig_size > 0 else 0
                        tqdm.write(
                            f"✓ {name}: {orig_size / (1024 * 1024):.2f}MB → "
                            f"{comp_size / (1024 * 1024):.2f}MB "
                            f"({compression_ratio:.1f}%, saved {saved / (1024 * 1024):.2f}MB)"
                        )
                    else:
                        failed += 1
                        tqdm.write(f"✗ Failed to compress {name}: {error}")

                except Exception as e:
                    failed += 1
                    tqdm.write(f"✗ Error compressing {folder_path.name}: {e}")

                pbar.update(1)

    # Summary
    total_compressed = successful + failed
    print("\n" + "=" * 60)
    print(f"COMPRESSION SUMMARY")
    print(f"  Total folders processed: {total_compressed}")
    print(f"  ✓ Successful: {successful}")
    print(f"  ✗ Failed: {failed}")
    if successful > 0:
        print(f"  Total space saved: {total_saved / (1024 * 1024):.2f} MB")
        print(f"  Average compression: {(total_saved / (successful * 1024 * 1024)):.2f} MB/folder")
    print(f"  Compressed files saved to: {root_dir}")
    print("=" * 60)


def process_files_decompress(root_dir: Path, threads: int = 2, max_workers: int = None):
    """
    Find and decompress all .tar.zst files in current directory.
    """
    if max_workers is None:
        max_workers = mp.cpu_count()

    # Find all .tar.zst files in current directory
    zst_files = list(root_dir.glob("*.tar.zst"))

    # Filter out temp files
    zst_files = [f for f in zst_files if not f.name.startswith("temp_")]

    if not zst_files:
        print(f"No .tar.zst files found in {root_dir}")
        return

    print(f"\nFound {len(zst_files)} compressed files to decompress")
    print(f"Using {threads} threads per worker, {max_workers} parallel workers\n")

    # Decompress files in parallel
    successful = 0
    failed = 0
    total_size = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(decompress_file, zst_path, root_dir, threads): zst_path for zst_path in zst_files
        }

        with tqdm(total=len(zst_files), desc="Decompressing", unit="file") as pbar:
            for future in as_completed(future_to_file):
                zst_path = future_to_file[future]
                try:
                    success, name, size, error = future.result()

                    if success:
                        successful += 1
                        total_size += size
                        tqdm.write(f"✓ {name}: extracted {size / (1024 * 1024):.2f}MB")
                    else:
                        failed += 1
                        tqdm.write(f"✗ Failed to decompress {name}: {error}")

                except Exception as e:
                    failed += 1
                    tqdm.write(f"✗ Error decompressing {zst_path.name}: {e}")

                pbar.update(1)

    # Summary
    total_processed = successful + failed
    print("\n" + "=" * 60)
    print(f"DECOMPRESSION SUMMARY")
    print(f"  Total files processed: {total_processed}")
    print(f"  ✓ Successful: {successful}")
    print(f"  ✗ Failed: {failed}")
    if successful > 0:
        print(f"  Total extracted data: {total_size / (1024 * 1024):.2f} MB")
        print(f"  Average extracted: {(total_size / (successful * 1024 * 1024)):.2f} MB/file")
    print(f"  Extracted to: {root_dir}")
    print("=" * 60)


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Compress or decompress folders using zstandard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compress folders >5MB in current directory
  python script.py -c
  
  # Compress with custom settings
  python script.py -c -m 10 -l 5 -t 4
  
  # Compress with custom skip directories
  python script.py -c --skip-dirs .git,dist,node_modules
  
  # Decompress all .tar.zst files
  python script.py -d
  
  # Decompress with custom threads
  python script.py -d -t 4
        """,
    )

    parser.add_argument("-c", "--compress", action="store_true", default=True, help="Compress folders (default)")
    parser.add_argument("-d", "--decompress", action="store_true", help="Decompress .tar.zst files")
    parser.add_argument(
        "-m", "--min-size", type=float, default=5, help="Minimum folder size in MB to compress (default: 5)"
    )
    parser.add_argument("-l", "--level", type=int, default=3, help="Zstandard compression level 1-22 (default: 3)")
    parser.add_argument("-t", "--threads", type=int, default=2, help="Threads per worker (default: 2)")
    parser.add_argument("-w", "--workers", type=int, default=None, help="Max parallel workers (default: CPU count)")
    parser.add_argument(
        "-p", "--path", type=str, default=".", help="Target directory path (default: current directory)"
    )
    parser.add_argument(
        "--skip-dirs",
        type=str,
        default=None,
        help="Comma-separated list of directories to skip (default: .git,dist,build,node_modules,__pycache__,.venv,venv)",
    )

    args = parser.parse_args()

    # Update skip directories if provided
    if args.skip_dirs:
        global SKIP_DIRS
        SKIP_DIRS = set(args.skip_dirs.split(","))

    # Determine mode
    if args.decompress and args.compress:
        # If both specified, decompress takes priority
        args.compress = False

    target_dir = Path(args.path).resolve()

    if not target_dir.exists():
        print(f"Error: Directory not found: {target_dir}")
        sys.exit(1)

    print(f"Working directory: {target_dir}")
    print(f"Mode: {'DECOMPRESS' if args.decompress else 'COMPRESS'}")
    if not args.decompress:
        print(f"Skip directories: {', '.join(sorted(SKIP_DIRS))}")
        print(f"Minimum size: {args.min_size}MB")
    print("-" * 60)

    try:
        if args.decompress:
            process_files_decompress(target_dir, args.threads, args.workers)
        else:
            process_folders_compress(target_dir, args.min_size, args.level, args.threads, args.workers)
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
