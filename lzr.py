#!/data/data/com.termux/files/usr/bin/python

import argparse
import asyncio
import mmap
import shutil
import sys
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import lz4.frame

# Use a bounded thread pool instead of semaphore
MAX_WORKERS = 4
CHUNK_SIZE = 524288  # 512KB
LZ4_COMPRESS_LEVEL = 9  # Maximum compression level (1-9, where 9 is best)
LZ4_ACCELERATION = 1  # Slowest/fastest compression (1 = slowest/max compression)


def decompress_file(path: Path) -> bool:
    """Decompress a single .lz4 file."""
    if not path.suffix == ".lz4":
        return False

    out_path = path.with_suffix("")  # Remove .lz4 extension

    try:
        compressed_data = path.read_bytes()
        if not compressed_data:
            return False

        decompressed_data = lz4.frame.decompress(compressed_data)
        out_path.write_bytes(decompressed_data)

        original_size = path.stat().st_size
        decompressed_size = out_path.stat().st_size

        print(f"  ✓ Decompressed {path.name}: {fsz(original_size)} → {fsz(decompressed_size)}")
        path.unlink()  # Remove compressed file after successful decompression
        return True

    except Exception as e:
        print(f"  ✗ Failed to decompress {path.name}: {e}")
        return False


def compress_in_memory(infile: Path, outfile: Path) -> bool:
    """Compress small files entirely in memory."""
    try:
        data = infile.read_bytes()
        if not data:
            return False

        # Use maximum compression with LZ4
        compressed = lz4.frame.compress(
            data,
            compression_level=LZ4_COMPRESS_LEVEL,
            mode="high_compression",  # Use HC mode for better compression
            acceleration=LZ4_ACCELERATION,
            content_checksum=True,  # Add checksum for integrity
            block_size=lz4.frame.BLOCKSIZE_MAX,  # Max block size for better compression
            block_linked=True,  # Link blocks for better compression
        )

        outfile.write_bytes(compressed)
        return True
    except (OSError, MemoryError, lz4.frame.LZ4FrameError) as e:
        print(f"Memory compression failed for {infile.name}: {e}")
        return False


def compress_chunk(data: bytes) -> bytes:
    """Compress a single chunk with max LZ4 settings."""
    return lz4.frame.compress(
        data,
        compression_level=LZ4_COMPRESS_LEVEL,
        mode="high_compression",
        acceleration=LZ4_ACCELERATION,
        content_checksum=True,
        block_size=lz4.frame.BLOCKSIZE_MAX,
        block_linked=True,
    )


def compress_chunked(in_path: Path, out_path: Path, file_size: int) -> bool:
    """Compress large files using chunked parallel processing."""
    try:
        chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        with (
            out_path.open("wb", buffering=1024 * 1024) as fout,
            in_path.open("rb") as fin,
            mmap.mmap(fin.fileno(), length=0, access=mmap.ACCESS_READ) as mm,
        ):
            # Create chunks lazily to save memory
            chunks = (mm[i * CHUNK_SIZE: min((i + 1) * CHUNK_SIZE, file_size)] for i in range(chunk_count))

            # Process chunks in parallel with bounded thread pool
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(compress_chunk, chunk): i for i, chunk in enumerate(chunks)}

                # Write results in order
                results = [None] * chunk_count
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        results[idx] = future.result()
                    except Exception as e:
                        print(f"Chunk {idx} compression failed: {e}")
                        return False

                # Write all compressed chunks in order
                # Note: Each chunk is a valid LZ4 frame that can be decompressed independently
                for compressed_chunk in results:
                    if compressed_chunk:
                        fout.write(compressed_chunk)
                    else:
                        return False

            return True
    except (OSError, MemoryError, lz4.frame.LZ4FrameError) as e:
        print(f"Chunked compression failed for {in_path.name}: {e}")
        return False


def fsz(size: float) -> str:
    """Format file size for human readable output."""
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if abs(size) < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PiB"


def create_tar_archive(source_dir: Path, output_path: Path) -> bool:
    """Create a tar archive from a directory using tarfile."""
    try:
        with tarfile.open(output_path, "w") as tar:
            # Add all files from the source directory
            for item in source_dir.rglob("*"):
                if item.is_file():
                    # Get relative path within the archive
                    arcname = item.relative_to(source_dir.parent)
                    tar.add(item, arcname=arcname)
        return True
    except Exception as e:
        print(f"  Failed to create tar archive: {e}")
        return False


def compress_tar_to_lz4(tar_path: Path, lz4_path: Path) -> bool:
    """Compress a tar file to tar.lz4 format."""
    try:
        tar_size = tar_path.stat().st_size

        # Choose compression strategy based on file size
        if tar_size < CHUNK_SIZE:
            success = compress_in_memory(tar_path, lz4_path)
        else:
            success = compress_chunked(tar_path, lz4_path, tar_size)

        if success and lz4_path.exists():
            lz4_size = lz4_path.stat().st_size
            if lz4_size == 0:
                print(f"Warning: Compressed archive empty for {tar_path.name}")
                lz4_path.unlink()
                return False

            # Only keep compressed version if it's smaller
            if lz4_size < tar_size:
                tar_path.unlink()  # Remove the intermediate .tar file
                reduction = (tar_size - lz4_size) / tar_size * 100
                print(f"  ✓ Compressed archive: {reduction:.1f}% saved ({fsz(tar_size)} → {fsz(lz4_size)})")
                return True
            else:
                print(f"  ✗ Archive compression didn't save space, keeping .tar")
                lz4_path.unlink()
                return False
        return False
    except Exception as e:
        print(f"  ✗ Failed to compress tar archive: {e}")
        return False


async def compress_folder_async(folder_path: Path, output_base_name: str) -> bool:
    """Compress a folder to tar archive, then compress to tar.lz4."""
    loop = asyncio.get_running_loop()
    tar_path = Path(output_base_name + ".tar")
    lz4_path = Path(output_base_name + ".tar.lz4")

    try:
        # Step 1: Create tar archive using tarfile
        print(f"  Creating tar archive...")
        success = await loop.run_in_executor(None, create_tar_archive, folder_path, tar_path)

        if not success or not tar_path.exists():
            print(f"  Failed to create tar archive")
            return False

        print(f"  Compressing tar archive with LZ4 (max compression)...")
        # Step 2: Compress tar to tar.lz4
        if compress_tar_to_lz4(tar_path, lz4_path):
            # Step 3: Remove original folder
            await loop.run_in_executor(None, shutil.rmtree, folder_path)
            return True
        else:
            # Keep the tar if compression failed
            return False

    except Exception as e:
        print(f"Failed to compress folder {folder_path.name}: {e}")
        # Clean up partial files
        if tar_path.exists():
            tar_path.unlink()
        if lz4_path.exists():
            lz4_path.unlink()
        return False


def compress_file(path: Path) -> tuple[bool, int, int]:
    """Compress a single file, returning (success, original_size, compressed_size)."""
    out_path = path.with_suffix(path.suffix + ".lz4")

    # Check if output already exists
    if out_path.exists():
        print(f"Skipping {path.name} - output already exists")
        return False, 0, 0

    try:
        original_size = path.stat().st_size
        if not original_size:
            return False, 0, 0

        # Choose compression strategy based on file size
        if original_size < CHUNK_SIZE:
            success = compress_in_memory(path, out_path)
        else:
            success = compress_chunked(path, out_path, original_size)

        if success and out_path.exists():
            compressed_size = out_path.stat().st_size
            if compressed_size == 0:
                print(f"Warning: Compressed file empty for {path.name}")
                out_path.unlink()
                return False, 0, 0

            # Only delete original if compression was beneficial
            if compressed_size < original_size:
                path.unlink()
                reduction = (original_size - compressed_size) / original_size * 100
                print(f"  ✓ {path.name}: {reduction:.1f}% saved ({fsz(original_size)} → {fsz(compressed_size)})")
                return True, original_size, compressed_size
            else:
                print(f"  ✗ {path.name}: No space saved, removing compressed file")
                out_path.unlink()
                return False, 0, 0
        else:
            return False, 0, 0

    except (OSError, PermissionError, lz4.frame.LZ4FrameError) as e:
        print(f"  ✗ Failed to compress {path.name}: {e}")
        return False, 0, 0


def get_files(directory: Path, mode: str = "compress") -> list[Path]:
    """Get all files that should be processed."""
    if mode == "compress":
        return [p for p in directory.glob("*") if p.is_file() and not p.is_symlink() and should_compress(p)]
    else:  # decompress mode
        return [p for p in directory.glob("*.lz4") if p.is_file() and not p.is_symlink()]


def get_dirs(directory: Path) -> list[Path]:
    """Get all subdirectories."""
    return [p for p in directory.glob("*") if not p.is_symlink() and p.is_dir()]


def should_compress(path: Path) -> bool:
    """Determine if a file should be compressed."""
    try:
        if not path.is_file() or path.is_symlink():
            return False

        # Skip already compressed files
        compressed_extensions = (".lz4", ".xz", ".gz", ".bz2", ".br", ".zst", ".7z", ".zip", ".rar")
        if path.suffix in compressed_extensions:
            return False

        # Skip very small files (under 1KB) - compression overhead not worth it
        size = path.stat().st_size
        return size >= 1024  # Only compress files >= 1KB

    except (OSError, PermissionError):
        return False


def extract_tar_archive(tar_path: Path, extract_dir: Path) -> bool:
    """Extract a tar archive using tarfile."""
    try:
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(path=extract_dir)
        return True
    except Exception as e:
        print(f"  Failed to extract tar archive: {e}")
        return False


async def process_compress() -> None:
    """Main compression routine."""
    cwd = Path.cwd()

    print(f"\n🔧 LZ4 Compression Settings:")
    print(f"   Level: {LZ4_COMPRESS_LEVEL}/9 (maximum)")
    print(f"   Mode: High Compression (HC)")
    print(f"   Acceleration: {LZ4_ACCELERATION} (slowest/max compression)")
    print(f"   Block size: Max (4MB)")
    print(f"   Block linking: Enabled")
    print(f"   Content checksum: Enabled")
    print(f"   Parallel workers: {MAX_WORKERS}")
    print(f"   Chunk size: {fsz(CHUNK_SIZE)}")

    # Process directories first
    dirs_to_compress = get_dirs(cwd)
    if dirs_to_compress:
        print(f"\n📁 Compressing {len(dirs_to_compress)} directories...")
        for dir_path in sorted(dirs_to_compress):
            relative_path = dir_path.relative_to(cwd)
            print(f"\n  Processing {relative_path}...")
            archive_path = str(dir_path.parent / dir_path.name)

            if await compress_folder_async(dir_path, archive_path):
                print(f"  ✓ Successfully compressed {relative_path} to {dir_path.name}.tar.lz4")
            else:
                print(f"  ✗ Failed to compress {relative_path}")

    # Process files
    files_to_compress = get_files(cwd, mode="compress")
    if not files_to_compress:
        print("\n📄 No files to compress")
        return

    print(f"\n📄 Compressing {len(files_to_compress)} files with LZ4 max compression...")

    total_original = 0
    total_compressed = 0
    successful = 0

    for i, path in enumerate(sorted(files_to_compress), 1):
        print(f"\n[{i}/{len(files_to_compress)}] {path.name}")
        success, orig_size, comp_size = compress_file(path)

        if success:
            successful += 1
            total_original += orig_size
            total_compressed += comp_size

    # Summary
    if successful > 0:
        savings = total_original - total_compressed
        savings_percent = (savings / total_original) * 100
        print(f"\n{'=' * 50}")
        print(f"✅ Compressed {successful}/{len(files_to_compress)} files")
        print(f"📊 Original size:  {fsz(total_original)}")
        print(f"📦 Compressed size: {fsz(total_compressed)}")
        print(f"💾 Space saved:    {fsz(savings)} ({savings_percent:.1f}%)")
        print(f"{'=' * 50}")
    elif files_to_compress:
        print("\n❌ No files were successfully compressed")


async def process_decompress() -> None:
    """Main decompression routine."""
    cwd = Path.cwd()

    # Process .tar.lz4 archives first (these are compressed folders)
    archives = [p for p in cwd.glob("*.tar.lz4") if p.is_file()]
    if archives:
        print(f"\n📦 Decompressing {len(archives)} archives...")
        for archive in sorted(archives):
            print(f"\n  Decompressing {archive.name}...")
            tar_path = None
            try:
                # First decompress the .lz4 to .tar
                tar_path = archive.with_suffix("")  # .tar
                print(f"    Decompressing LZ4...")
                compressed_data = archive.read_bytes()
                tar_data = lz4.frame.decompress(compressed_data)
                tar_path.write_bytes(tar_data)

                # Then extract the .tar
                extract_dir = archive.stem  # Remove .tar.lz4
                print(f"    Extracting tar to {extract_dir}/...")

                loop = asyncio.get_running_loop()
                success = await loop.run_in_executor(None, extract_tar_archive, tar_path, Path(extract_dir))

                if success:
                    # Clean up
                    tar_path.unlink()
                    archive.unlink()
                    print(f"  ✓ Extracted {archive.name} to {extract_dir}/")
                else:
                    print(f"  ✗ Failed to extract {archive.name}")

            except Exception as e:
                print(f"  ✗ Failed to decompress {archive.name}: {e}")
                # Clean up partial files
                if tar_path and tar_path.exists():
                    tar_path.unlink()

    # Process individual .lz4 files
    files_to_decompress = get_files(cwd, mode="decompress")
    if not files_to_decompress:
        print("\n📄 No .lz4 files to decompress")
        return

    # Filter out .tar.lz4 files as they're handled above
    files_to_decompress = [p for p in files_to_decompress if p.suffixes != [".tar", ".lz4"]]

    if not files_to_decompress:
        return

    print(f"\n📄 Decompressing {len(files_to_decompress)} LZ4 files...")

    total_original = 0
    total_decompressed = 0
    successful = 0

    for i, path in enumerate(sorted(files_to_decompress), 1):
        print(f"\n[{i}/{len(files_to_decompress)}] {path.name}")
        original_size = path.stat().st_size
        total_original += original_size

        if decompress_file(path):
            successful += 1
            out_path = path.with_suffix("")
            if out_path.exists():
                total_decompressed += out_path.stat().st_size

    # Summary
    if successful > 0:
        print(f"\n{'=' * 50}")
        print(f"✅ Decompressed {successful}/{len(files_to_decompress)} files")
        print(f"📦 Compressed size:   {fsz(total_original)}")
        print(f"📊 Decompressed size: {fsz(total_decompressed)}")
        print(f"{'=' * 50}")
    elif files_to_decompress:
        print("\n❌ No files were successfully decompressed")


async def main_async(mode: str = "compress") -> None:
    """Main async entry point."""
    if mode == "compress":
        await process_compress()
    elif mode == "decompress":
        await process_decompress()
    else:
        print(f"Unknown mode: {mode}")


def main() -> None:
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Multi-threaded LZ4 compression/decompression tool (max compression)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -c          # Compress files and folders in current directory
  %(prog)s -d          # Decompress .lz4 and .tar.lz4 files in current directory
  %(prog)s             # Default: compress

LZ4 Settings:
  - Level: 9 (maximum high compression)
  - Mode: High Compression (HC) for better ratios
  - Acceleration: 1 (slowest/max compression)
  - Block size: 4MB (maximum)
  - Content checksum: Enabled for integrity
  - Use case: Excellent balance of speed and compression
  - Note: Decompression is extremely fast (often > 500 MB/s)
        """,
    )

    # Create mutually exclusive group for compress/decompress
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c", "--compress", action="store_true", help="Compress files and folders with LZ4 (default)")
    group.add_argument("-d", "--decompress", action="store_true", help="Decompress .lz4 and .tar.lz4 files")

    args = parser.parse_args()

    # Determine mode
    if args.decompress:
        mode = "decompress"
    else:
        mode = "compress"  # Default mode

    try:
        asyncio.run(main_async(mode))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
