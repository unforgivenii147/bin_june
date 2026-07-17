#!/data/data/com.termux/files/usr/bin/env python

import argparse
import asyncio
import bz2
import gzip
import sys
from collections import deque
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

try:
    import zstandard as zstd

    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
try:
    import brotli

    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False
try:
    import py7zr

    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False
try:
    import lz4.frame

    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False


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
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


def get_dirs(directory: Path) -> list[Path]:
    return [p for p in directory.glob("*") if not p.is_symlink() and p.is_dir()]


def should_compress(path: Path, compressor: str) -> bool:
    try:
        if not path.is_file() or path.is_symlink():
            return False
        compressed_extensions = (".xz", ".gz", ".bz2", ".br", ".zst", ".7z", ".zip", ".rar", ".lz4")
        if path.suffix in compressed_extensions:
            return False
        size = path.stat().st_size
        return size >= 1024
    except (OSError, PermissionError):
        return False


async def process_compress(compressor: str) -> None:
    cwd = Path.cwd()
    print(f"\n🔧 {compressor.upper()} Compression Settings:")
    for key, value in COMPRESSORS[compressor]["settings"].items():
        print(f"   {key}: {value}")
    print(f"   Parallel workers: {MAX_WORKERS}")
    print(f"   Chunk size: {fsz(CHUNK_SIZE)}")
    dirs_to_compress = get_dirs(cwd)
    if dirs_to_compress:
        print(f"\n📁 Compressing {len(dirs_to_compress)} directories...")
        for dir_path in sorted(dirs_to_compress):
            relative_path = dir_path.relative_to(cwd)
            print(f"\n  Processing {relative_path}...")
            archive_path = str(dir_path.parent / dir_path.name)
            if await compress_folder_async(dir_path, archive_path, compressor):
                print(f"  ✓ Successfully compressed {relative_path}")
            else:
                print(f"  ✗ Failed to compress {relative_path}")
    files_to_compress = get_files(cwd, compressor, mode="compress")
    if not files_to_compress:
        print("\n📄 No files to compress")
        return
    print(f"\n📄 Compressing {len(files_to_compress)} files with {compressor.upper()}...")
    total_original = 0
    total_compressed = 0
    successful = 0
    for i, path in enumerate(sorted(files_to_compress), 1):
        print(f"\n[{i}/{len(files_to_compress)}] {path.name}")
        original_size = path.stat().st_size
        total_original += original_size
        out_path = path.with_suffix(path.suffix + COMPRESSORS[compressor]["ext"])
        if out_path.exists():
            print(f"Skipping {path.name} - output already exists")
            continue
        if original_size < CHUNK_SIZE:
            success = compress_in_memory(path, out_path, compressor)
        else:
            success = compress_chunked(path, out_path, original_size, compressor)
        if success and out_path.exists():
            compressed_size = out_path.stat().st_size
            if compressed_size > 0 and compressed_size < original_size:
                path.unlink()
                reduction = (original_size - compressed_size) / original_size * 100
                print(f"  ✓ {path.name}: {reduction:.1f}% saved ({fsz(original_size)} → {fsz(compressed_size)})")
                successful += 1
                total_compressed += compressed_size
            else:
                print(f"  ✗ {path.name}: No space saved, removing compressed file")
                out_path.unlink()
        else:
            print(f"  ✗ Failed to compress {path.name}")
    if successful > 0:
        savings = total_original - total_compressed
        savings_percent = savings / total_original * 100
        print(f"\n{'=' * 50}")
        print(f"✅ Compressed {successful}/{len(files_to_compress)} files")
        print(f"📊 Original size:  {fsz(total_original)}")
        print(f"📦 Compressed size: {fsz(total_compressed)}")
        print(f"💾 Space saved:    {fsz(savings)} ({savings_percent:.1f}%)")
        print(f"{'=' * 50}")
    elif files_to_compress:
        print("\n❌ No files were successfully compressed")


async def process_decompress(compressor: str) -> None:
    cwd = Path.cwd()
    archive_ext = COMPRESSORS[compressor]["tar_ext"]
    archives = [p for p in cwd.glob(f"*{archive_ext}") if p.is_file()]
    if archives:
        print(f"\n📦 Decompressing {len(archives)} archives...")
        for archive in sorted(archives):
            print(f"\n  Decompressing {archive.name}...")
            decompress_archive(archive, compressor)
    files_to_decompress = get_files(cwd, compressor, mode="decompress")
    if not files_to_decompress:
        print("\n📄 No files to decompress")
        return
    files_to_decompress = [p for p in files_to_decompress if not p.name.endswith(COMPRESSORS[compressor]["tar_ext"])]
    if not files_to_decompress:
        return
    print(f"\n📄 Decompressing {len(files_to_decompress)} {compressor.upper()} files...")
    total_original = 0
    total_decompressed = 0
    successful = 0
    for i, path in enumerate(sorted(files_to_decompress), 1):
        print(f"\n[{i}/{len(files_to_decompress)}] {path.name}")
        original_size = path.stat().st_size
        total_original += original_size
        if decompress_file(path, compressor):
            successful += 1
            out_path = path.with_suffix("")
            if out_path.exists():
                total_decompressed += out_path.stat().st_size
    if successful > 0:
        print(f"\n{'=' * 50}")
        print(f"✅ Decompressed {successful}/{len(files_to_decompress)} files")
        print(f"📦 Compressed size:   {fsz(total_original)}")
        print(f"📊 Decompressed size: {fsz(total_decompressed)}")
        print(f"{'=' * 50}")
    elif files_to_decompress:
        print("\n❌ No files were successfully decompressed")


async def main_async(compressor: str, mode: str = "compress") -> None:
    if mode == "compress":
        await process_compress(compressor)
    elif mode == "decompress":
        await process_decompress(compressor)
    else:
        print(f"Unknown mode: {mode}")


def check_compressor_availability(compressor: str) -> bool:
    if not COMPRESSORS[compressor]["available"]:
        print(f"\n❌ Error: {compressor.upper()} compression is not available.")
        print(f"Please install the required library:")
        if compressor == "zstd":
            print("  pip install zstandard")
            print("  or for Termux: pkg install python-zstandard")
        elif compressor == "brotli":
            print("  pip install brotli")
            print("  or for Termux: pkg install python-brotli")
        elif compressor == "py7zr":
            print("  pip install py7zr")
            print("  or for Termux: pkg install python-py7zr")
        elif compressor == "lz4":
            print("  pip install lz4")
            print("  or for Termux: pkg install python-lz4")
        return False
    return True


def main() -> None:
    setup_compressors()
    parser = argparse.ArgumentParser(
        description="Multi-format compression/decompression tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Compression Methods:
  -z, --zstd     Zstandard compression (max level 22)
  -x, --xz       LZMA/XZ compression (preset 9)
  -7, --7z       7-Zip compression (LZMA2 max)
  -g, --gzip     Gzip compression (level 9)
  -b, --bz2      Bzip2 compression (level 9)
  -l, --lz4      LZ4 compression (HC mode max)

Examples:
  %(prog)s -z              # Compress with Zstandard (default)
  %(prog)s -x -d           # Decompress XZ files
  %(prog)s -7              # Compress with 7-Zip
  %(prog)s -g              # Compress with Gzip
  %(prog)s -b -d           # Decompress Bzip2 files
  %(prog)s -l              # Compress with LZ4
        """,
    )
    method_group = parser.add_mutually_exclusive_group()
    method_group.add_argument("-z", "--zstd", action="store_true", help="Use Zstandard compression")
    method_group.add_argument("-x", "--xz", action="store_true", help="Use XZ/LZMA compression")
    method_group.add_argument("-7", "--7z", action="store_true", help="Use 7-Zip compression")
    method_group.add_argument("-g", "--gzip", action="store_true", help="Use Gzip compression")
    method_group.add_argument("-b", "--bz2", action="store_true", help="Use Bzip2 compression")
    method_group.add_argument("-l", "--lz4", action="store_true", help="Use LZ4 compression")
    parser.add_argument("-d", "--decompress", action="store_true", help="Decompress files")
    args = parser.parse_args()
    compressor = "zstd"
    if args.xz:
        compressor = "xz"
    elif args.gz or args.gzip:
        compressor = "gzip"
    elif args.bz2:
        compressor = "bz2"
    elif args.zstd:
        compressor = "zstd"
    elif args.lz4:
        compressor = "lz4"
    elif args.seven or args["7z"]:
        compressor = "py7zr"
    if not check_compressor_availability(compressor):
        sys.exit(1)
    mode = "decompress" if args.decompress else "compress"
    try:
        asyncio.run(main_async(compressor, mode))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
