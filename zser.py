#!/data/data/com.termux/files/usr/bin/env python
"""
zser_optimized_by_gemini.py – Parallel Zstandard compressor/decompressor.
Optimized for Python 3.12 with modern syntax, type hints, and performance improvements.
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing
import shutil
import sys
import tarfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from typing import Final

import zstandard as zstd

# Constants
ZST_EXT: Final[str] = ".zst"
SKIP_EXTS: Final[frozenset[str]] = frozenset({
    ".xz",
    ".br",
    ".7z",
    ".zip",
    ".gz",
    ".bz2",
    ".zst",
    ".whl",
    ".mp4",
    ".mp3",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".webm",
})
SKIP_DIRS: Final[frozenset[str]] = frozenset({".git", "__pycache__", ".ruff_cache", ".pytest_cache", ".mypy_cache"})
MAX_WORKERS: Final[int] = max(1, multiprocessing.cpu_count())

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)


def fsize(num: float) -> str:
    """Format size in human-readable units."""
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def get_dir_size(path: Path) -> int:
    """Recursively calculate directory size."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


def compress_file(path: Path, level: int = 21) -> dict:
    """Compress a single file."""
    dst = path.with_suffix(path.suffix + ZST_EXT)
    if dst.exists():
        return {"status": "skip", "path": str(path)}
    try:
        size = path.stat().st_size
        if size == 0:
            path.unlink()
            return {"status": "skip", "path": str(path), "reason": "empty"}

        cctx = zstd.ZstdCompressor(level=level, write_content_size=True)
        data = path.read_bytes()
        compressed = cctx.compress(data)
        dst.write_bytes(compressed)
        path.unlink()
        return {"status": "ok", "path": str(path), "original": size, "compressed": len(compressed)}
    except Exception as e:
        dst.unlink(missing_ok=True)
        return {"status": "error", "path": str(path), "error": str(e)}


def decompress_file(path: Path) -> dict:
    """Decompress a single file."""
    if path.suffix != ZST_EXT:
        return {"status": "skip", "path": str(path)}
    dst = path.with_suffix("")
    if dst.exists():
        return {"status": "skip", "path": str(path)}
    try:
        dctx = zstd.ZstdDecompressor()
        data = path.read_bytes()
        decompressed = dctx.decompress(data)
        dst.write_bytes(decompressed)

        if dst.suffix == ".tar":
            try:
                with tarfile.open(dst, "r") as tar:
                    tar.extractall(path=dst.parent)
                dst.unlink()
                path.unlink()
                return {
                    "status": "ok",
                    "path": str(path),
                    "extracted": True,
                    "original": len(data),
                    "decompressed": len(decompressed),
                }
            except Exception as e:
                return {"status": "error", "path": str(path), "error": f"tar extract: {e}"}

        path.unlink()
        return {
            "status": "ok",
            "path": str(path),
            "dst": str(dst),
            "original": len(data),
            "decompressed": len(decompressed),
        }
    except Exception as e:
        dst.unlink(missing_ok=True)
        return {"status": "error", "path": str(path), "error": str(e)}


def compress_dir(path: Path, level: int = 21) -> dict:
    """Archive and compress a directory."""
    zst_path = path.with_name(f"{path.name}.tar{ZST_EXT}")
    try:
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            tar.add(path, arcname=path.name)

        tar_data = buf.getvalue()
        cctx = zstd.ZstdCompressor(level=level, write_content_size=True)
        compressed = cctx.compress(tar_data)
        orig_size = get_dir_size(path)
        zst_path.write_bytes(compressed)
        shutil.rmtree(path)
        return {"status": "ok", "path": str(path), "original": orig_size, "compressed": len(compressed)}
    except Exception as e:
        zst_path.unlink(missing_ok=True)
        return {"status": "error", "path": str(path), "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="zser – modern parallel Zstandard compressor")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c", "--compress", action="store_true", default=True)
    group.add_argument("-d", "--decompress", action="store_true")
    parser.add_argument("-l", "--level", type=int, default=21, help="Compression level (1-22)")
    parser.add_argument("-w", "--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("-p", "--path", type=Path, default=Path.cwd())
    parser.add_argument("--no-dirs", action="store_true")
    args = parser.parse_args()

    target = args.path.resolve()
    if not target.is_dir():
        logger.error("Target must be a directory")
        return 1

    initial_size = get_dir_size(target)
    mode = "decompress" if args.decompress else "compress"
    logger.info(f"zser - {mode} | {target} | workers={args.workers} | size={fsize(initial_size)}")

    if args.decompress:
        files = list(target.glob(f"*{ZST_EXT}"))
        if not files:
            logger.info("No .zst files found")
            return 0

        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(decompress_file, f) for f in files]
            for fut in as_completed(futures):
                res = fut.result()
                if res["status"] == "ok":
                    logger.info(f"  ✓ {Path(res['path']).name}")
    else:
        if not args.no_dirs:
            dirs = [p for p in target.iterdir() if p.is_dir() and p.name not in SKIP_DIRS]
            for d in dirs:
                logger.info(f"  dir  {d.name}...")
                res = compress_dir(d, args.level)
                if res["status"] == "ok":
                    logger.info(f"    ✓ {fsize(res['original'])} → {fsize(res['compressed'])}")

        files = [p for p in target.iterdir() if p.is_file() and p.suffix not in SKIP_EXTS]
        if files:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(compress_file, f, args.level) for f in files]
                for fut in as_completed(futures):
                    res = fut.result()
                    if res["status"] == "ok":
                        logger.info(
                            f"  ✓ {Path(res['path']).name}: {fsize(res['original'])} → {fsize(res['compressed'])}"
                        )
        else:
            logger.info("Nothing to compress")

    final_size = get_dir_size(target)
    logger.info(f"\nFinal size: {fsize(final_size)} (saved {fsize(initial_size - final_size)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
