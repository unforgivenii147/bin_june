#!/data/data/com.termux/files/usr/bin/env python


"""
zsr_optimized_by_gemini.py — Multi-threaded Zstandard compression/decompression tool.
Optimized for Python 3.12 with modern syntax, type hints, and performance improvements.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import mmap
import multiprocessing
import shutil
import sys
import tarfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Final

import zstandard as zstd

CHUNK_SIZE = 1024 * 1024

SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
)
MAX_WORKERS: Final[int] = max(1, multiprocessing.cpu_count())
CHUNK_SIZE: Final[int] = 512 * 1024
ZSTD_LEVEL: Final[int] = 22
ZSTD_THREADS: Final[int] = 4
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)


def fsz(size: float) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if abs(size) < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PiB"


def compress_chunk(data: bytes) -> bytes:
    compressor = zstd.ZstdCompressor(level=ZSTD_LEVEL, threads=1)
    return compressor.compress(data)


def compress_chunked(in_path: Path, out_path: Path, file_size: int) -> bool:
    try:
        chunk_count = (file_size + 32768 - 1) // 32768
        with (
            out_path.open("wb", buffering=1024 * 1024) as fout,
            in_path.open("rb") as fin,
            mmap.mmap(fin.fileno(), length=0, access=mmap.ACCESS_READ) as mm,
        ):
            chunks = (mm[i * 32768 : min((i + 1) * 32768, file_size)] for i in range(chunk_count))
            with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(compress_chunk, bytes(chunk)): i for i, chunk in enumerate(chunks)}
                results = [None] * chunk_count
                for future in as_completed(futures):
                    idx = futures[future]
                    results[idx] = future.result()
                for compressed_chunk in results:
                    if compressed_chunk:
                        fout.write(compressed_chunk)
                    else:
                        return False
            return True
    except Exception as e:
        logger.error(f"Chunked compression failed for {in_path.name}: {e}")
        return False


def compress_in_memory(infile: Path, outfile: Path) -> bool:
    try:
        data = infile.read_bytes()
        if not data:
            return False
        compressor = zstd.ZstdCompressor(level=ZSTD_LEVEL, threads=ZSTD_THREADS)
        compressed = compressor.compress(data)
        outfile.write_bytes(compressed)
        return True
    except Exception as e:
        logger.error(f"Memory compression failed for {infile.name}: {e}")
        return False


def compress_file(path: Path) -> tuple[bool, int, int]:
    out_path = path.with_suffix(path.suffix + ".zst")
    if out_path.exists():
        logger.info(f"Skipping {path.name} - output already exists")
        return (False, 0, 0)
    try:
        original_size = path.stat().st_size
        if original_size == 0:
            return (False, 0, 0)
        if original_size < CHUNK_SIZE:
            success = compress_in_memory(path, out_path)
        else:
            success = compress_chunked(path, out_path, original_size)
        if success and out_path.exists():
            compressed_size = out_path.stat().st_size
            if compressed_size < original_size:
                path.unlink()
                reduction = (original_size - compressed_size) / original_size * 100
                logger.info(f"  ✓ {path.name}: {reduction:.1f}% saved ({fsz(original_size)} → {fsz(compressed_size)})")
                return (True, original_size, compressed_size)
            else:
                logger.info(f"  ✗ {path.name}: No space saved, removing compressed file")
                out_path.unlink()
                return (False, 0, 0)
    except Exception as e:
        logger.error(f"  ✗ Failed to compress {path.name}: {e}")
    return (False, 0, 0)


def decompress_file(path: Path) -> bool:
    if path.suffix != ".zst":
        return False
    out_path = path.with_suffix("")
    try:
        dctx = zstd.ZstdDecompressor()
        with path.open("rb") as f_in, out_path.open("wb") as f_out:
            dctx.copy_stream(f_in, f_out)
        original_size = path.stat().st_size
        decompressed_size = out_path.stat().st_size
        logger.info(f"  ✓ Decompressed {path.name}: {fsz(original_size)} → {fsz(decompressed_size)}")
        path.unlink()
        return True
    except Exception as e:
        logger.error(f"  ✗ Failed to decompress {path.name}: {e}")
        return False


def create_tar_archive(source_dir: Path, output_path: Path) -> bool:
    try:
        with tarfile.open(output_path, "w") as tar:
            tar.add(source_dir, arcname=source_dir.name)
        return True
    except Exception as e:
        logger.error(f"  Failed to create tar archive: {e}")
        return False


async def compress_folder_async(folder_path: Path, output_base_name: str) -> bool:
    loop = asyncio.get_running_loop()
    tar_path = Path(f"{output_base_name}.tar")
    zst_path = Path(f"{output_base_name}.tar.zst")
    try:
        logger.info(f"  Creating tar archive for {folder_path.name}...")
        success = await loop.run_in_executor(None, create_tar_archive, folder_path, tar_path)
        if not success or not tar_path.exists():
            return False
        logger.info("  Compressing tar archive with Zstandard...")
        tar_size = tar_path.stat().st_size
        if tar_size < CHUNK_SIZE:
            success = await loop.run_in_executor(None, compress_in_memory, tar_path, zst_path)
        else:
            success = await loop.run_in_executor(None, compress_chunked, tar_path, zst_path, tar_size)
        if success and zst_path.exists():
            zst_size = zst_path.stat().st_size
            if zst_size < tar_size:
                tar_path.unlink()
                reduction = (tar_size - zst_size) / tar_size * 100
                logger.info(f"  ✓ Compressed archive: {reduction:.1f}% saved ({fsz(tar_size)} → {fsz(zst_size)})")
                await loop.run_in_executor(None, shutil.rmtree, folder_path)
                return True
            else:
                logger.info("  ✗ Archive compression didn't save space")
                zst_path.unlink()
        return False
    except Exception as e:
        logger.error(f"Failed to compress folder {folder_path.name}: {e}")
        return False


async def process_compress() -> None:
    cwd = Path.cwd()
    logger.info(f"\n🔧 Zstandard Compression Settings (Level {ZSTD_LEVEL})")
    dirs = [p for p in cwd.iterdir() if p.is_dir() and p.name not in SKIP_DIRS]
    if dirs:
        logger.info(f"\n📁 Compressing {len(dirs)} directories...")
        for d in sorted(dirs):
            await compress_folder_async(d, str(d))
    files = [
        p
        for p in cwd.iterdir()
        if p.is_file() and (p.suffix not in (".zst", ".tar", ".gz", ".zip")) and (p.stat().st_size >= 1024)
    ]
    if files:
        logger.info(f"\n📄 Compressing {len(files)} files...")
        total_orig = total_comp = successful = 0
        for i, f in enumerate(sorted(files), 1):
            logger.info(f"[{i}/{len(files)}] {f.name}")
            success, o_sz, c_sz = compress_file(f)
            if success:
                successful += 1
                total_orig += o_sz
                total_comp += c_sz
        if successful > 0:
            saved = total_orig - total_comp
            logger.info(
                f"\n{'=' * 50}\n✅ Compressed {successful} files\n📊 Saved {fsz(saved)} ({saved / total_orig * 100:.1f}%)\n{'=' * 50}"
            )


async def process_decompress() -> None:
    cwd = Path.cwd()
    archives = list(cwd.glob("*.tar.zst"))
    if archives:
        logger.info(f"\n📦 Decompressing {len(archives)} archives...")
        for arch in sorted(archives):
            logger.info(f"  Processing {arch.name}...")
            tar_path = arch.with_suffix("")
            try:
                dctx = zstd.ZstdDecompressor()
                with arch.open("rb") as f_in, tar_path.open("wb") as f_out:
                    dctx.copy_stream(f_in, f_out)
                extract_dir = arch.name.removesuffix(".tar.zst")
                with tarfile.open(tar_path, "r") as tar:
                    tar.extractall(path=Path(extract_dir))
                tar_path.unlink()
                arch.unlink()
                logger.info(f"  ✓ Extracted to {extract_dir}/")
            except Exception as e:
                logger.error(f"  ✗ Failed to decompress {arch.name}: {e}")
    zst_files = [p for p in cwd.glob("*.zst") if not p.name.endswith(".tar.zst")]
    if zst_files:
        logger.info(f"\n📄 Decompressing {len(zst_files)} files...")
        for f in sorted(zst_files):
            decompress_file(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Modern Zstandard compression tool")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c", "--compress", action="store_true", default=True)
    group.add_argument("-d", "--decompress", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(process_decompress() if args.decompress else process_compress())
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")


if __name__ == "__main__":
    main()