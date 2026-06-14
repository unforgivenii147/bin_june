#!/data/data/com.termux/files/usr/bin/python

import argparse
import asyncio
import mmap
import shutil
import sys
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import zstandard as zstd

# Use a bounded thread pool instead of semaphore
MAX_WORKERS = 4
CHUNK_SIZE = 524288  # 512KB
ZSTD_LEVEL = 22  # Maximum compression level (1-22, where 22 is best)
ZSTD_THREADS = 4  # Threads for zstd compression (internal threading)


def decompress_file(path: Path) -> bool:
    """Decompress a single .zst file."""
    if not path.suffix == ".zst":
        return False

    out_path = path.with_suffix("")  # Remove .zst extension

    try:
        compressed_data = path.read_bytes()
        if not compressed_data:
            return False

        decompressed_data = zstd.decompress(compressed_data)
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

        # Create compressor with max compression settings
        compressor = zstd.ZstdCompressor(level=ZSTD_LEVEL, threads=ZSTD_THREADS)
        compressed = compressor.compress(data)

        outfile.write_bytes(compressed)
        return True
    except (OSError, MemoryError, zstd.ZstdError) as e:
        print(f"Memory compression failed for {infile.name}: {e}")
        return False


def compress_chunk(data: bytes) -> bytes:
    """Compress a single chunk with max zstd settings."""
    compressor = zstd.ZstdCompressor(level=ZSTD_LEVEL, threads=1)  # Single thread for chunks
    return compressor.compress(data)


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
                for compressed_chunk in results:
                    if compressed_chunk:
                        fout.write(compressed_chunk)
                    else:
                        return False

            return True
    except (OSError, MemoryError, zstd.ZstdError) as e:
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


def compress_tar_to_zst(tar_path: Path, zst_path: Path) -> bool:
    """Compress a tar file to tar.zst format."""
    try:
        tar_size = tar_path.stat().st_size

        # Choose compression strategy based on file size
        if tar_size < CHUNK_SIZE:
            success = compress_in_memory(tar_path, zst_path)
        else:
            success = compress_chunked(tar_path, zst_path, tar_size)

        if success and zst_path.exists():
            zst_size = zst_path.stat().st_size
            if zst_size == 0:
                print(f"Warning: Compressed archive empty for {tar_path.name}")
                zst_path.unlink()
                return False

            # Only keep compressed version if it's smaller
            if zst_size < tar_size:
                tar_path.unlink()  # Remove the intermediate .tar file
                reduction = (tar_size - zst_size) / tar_size * 100
                print(f"  ✓ Compressed archive: {reduction:.1f}% saved ({fsz(tar_size)} → {fsz(zst_size)})")
                return True
            else:
                print(f"  ✗ Archive compression didn't save space, keeping .tar")
                zst_path.unlink()
                return False
        return False
    except Exception as e:
        print(f"  ✗ Failed to compress tar archive: {e}")
        return False


async def compress_folder_async(folder_path: Path, output_base_name: str) -> bool:
    """Compress a folder to tar archive, then compress to tar.zst."""
    loop = asyncio.get_running_loop()
    tar_path = Path(output_base_name + ".tar")
    zst_path = Path(output_base_name + ".tar.zst")

    try:
        # Step 1: Create tar archive using tarfile
        print(f"  Creating tar archive...")
        success = await loop.run_in_executor(None, create_tar_archive, folder_path, tar_path)

        if not success or not tar_path.exists():
            print(f"  Failed to create tar archive")
            return False

        print(f"  Compressing tar archive with Zstandard (max level {ZSTD_LEVEL})...")
        # Step 2: Compress tar to tar.zst
        if compress_tar_to_zst(tar_path, zst_path):
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
        if zst_path.exists():
            zst_path.unlink()
        return False


def compress_file(path: Path) -> tuple[bool, int, int]:
    """Compress a single file, returning (success, original_size, compressed_size)."""
    out_path = path.with_suffix(path.suffix + ".zst")

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

    except (OSError, PermissionError, zstd.ZstdError) as e:
        print(f"  ✗ Failed to compress {path.name}: {e}")
        return False, 0, 0


def get_files(directory: Path, mode: str = "compress") -> list[Path]:
    """Get all files that should be processed."""
    if mode == "compress":
        return [p for p in directory.glob("*") if p.is_file() and not p.is_symlink() and should_compress(p)]
    else:  # decompress mode
        return [p for p in directory.glob("*.zst") if p.is_file() and not p.is_symlink()]


def get_dirs(directory: Path) -> list[Path]:
    """Get all subdirectories."""
    return [p for p in directory.glob("*") if not p.is_symlink() and p.is_dir()]


def should_compress(path: Path) -> bool:
    """Determine if a file should be compressed."""
    try:
        if not path.is_file() or path.is_symlink():
            return False

        # Skip already compressed files
        compressed_extensions = (".zst", ".xz", ".gz", ".bz2", ".br", ".7z", ".zip", ".tar")
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

    print(f"\n🔧 Zstandard Compression Settings:")
    print(f"   Level: {ZSTD_LEVEL}/22 (maximum)")
    print(f"   Threads: {ZSTD_THREADS} (internal) + {MAX_WORKERS} (parallel chunks)")
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
                print(f"  ✓ Successfully compressed {relative_path} to {dir_path.name}.tar.zst")
            else:
                print(f"  ✗ Failed to compress {relative_path}")

    # Process files
    files_to_compress = get_files(cwd, mode="compress")
    if not files_to_compress:
        print("\n📄 No files to compress")
        return

    print(f"\n📄 Compressing {len(files_to_compress)} files with Zstandard max compression...")

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

    # Process .tar.zst archives first (these are compressed folders)
    archives = [p for p in cwd.glob("*.tar.zst") if p.is_file()]
    if archives:
        print(f"\n📦 Decompressing {len(archives)} archives...")
        for archive in sorted(archives):
            print(f"\n  Decompressing {archive.name}...")
            tar_path = None
            try:
                # First decompress the .zst to .tar
                tar_path = archive.with_suffix("")  # .tar
                print(f"    Decompressing Zstandard...")
                compressed_data = archive.read_bytes()
                tar_data = zstd.decompress(compressed_data)
                tar_path.write_bytes(tar_data)

                # Then extract the .tar
                extract_dir = archive.stem  # Remove .tar.zst
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

    # Process individual .zst files
    files_to_decompress = get_files(cwd, mode="decompress")
    if not files_to_decompress:
        print("\n📄 No .zst files to decompress")
        return

    # Filter out .tar.zst files as they're handled above
    files_to_decompress = [p for p in files_to_decompress if p.suffixes != [".tar", ".zst"]]

    if not files_to_decompress:
        return

    print(f"\n📄 Decompressing {len(files_to_decompress)} Zstandard files...")

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
        description="Multi-threaded Zstandard compression/decompression tool (max compression)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -c          # Compress files and folders in current directory
  %(prog)s -d          # Decompress .zst and .tar.zst files in current directory
  %(prog)s             # Default: compress

Zstandard Settings:
  - Level: 22/22 (maximum compression)
  - Threads: 4 (internal threading support)
  - Dictionary: None (adaptive mode)
        """,
    )

    # Create mutually exclusive group for compress/decompress
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-c", "--compress", action="store_true", help="Compress files and folders with Zstandard (default)"
    )
    group.add_argument("-d", "--decompress", action="store_true", help="Decompress .zst and .tar.zst files")

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
