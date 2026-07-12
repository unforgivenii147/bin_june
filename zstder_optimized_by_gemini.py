#!/usr/bin/env python3
"""
zstder_optimized_by_gemini.py — Recursive Zstandard compression/decompression tool.
Optimized for Python 3.12 with modern syntax, type hints, and performance improvements.
"""

import argparse
import logging
import multiprocessing
import shutil
import sys
import tarfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Final

import zstandard as zstd

# Constants
SKIP_DIRS: Final[frozenset[str]] = frozenset({
    "lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"
})
LARGE_FILE_THRESHOLD: Final[int] = 5 * 1024 * 1024
LEVEL_DEFAULT: Final[int] = 19
LEVEL_LARGE: Final[int] = 9
ZSTD_EXT: Final[str] = ".zst"
DEFAULT_THREADS: Final[int] = 4
WORKERS: Final[int] = max(1, multiprocessing.cpu_count())

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def choose_level(path: Path) -> int:
    """Choose compression level based on file size."""
    try:
        return LEVEL_LARGE if path.stat().st_size > LARGE_FILE_THRESHOLD else LEVEL_DEFAULT
    except OSError:
        return LEVEL_DEFAULT

def human_size(n: float) -> str:
    """Convert bytes to human-readable format."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def ratio_str(before: int, after: int) -> str:
    """Calculate compression ratio as a percentage string."""
    if before == 0:
        return "0%"
    return f"{(after / before) * 100:.1f}%"

def status_line(ok: bool, name: str, elapsed_ms: float, before: int, after: int) -> str:
    """Generate a status line for logging."""
    icon = "✔" if ok else "✘"
    return f"[{icon}] {name} ({elapsed_ms:.0f}ms) {ratio_str(before, after)}"

def compress_file(
    src: Path, 
    dry_run: bool, 
    verbose: bool, 
    level: int | None = None, 
    threads: int = DEFAULT_THREADS
) -> dict:
    """Compress a single file using Zstandard."""
    result = {"src": src, "ok": False, "line": "", "msg": ""}
    dst = src.with_suffix(src.suffix + ZSTD_EXT)
    
    if dst.exists():
        result["line"] = f"[–] {src.name} (skipped — {dst.name} exists)"
        return result
        
    effective_level = level if level is not None else choose_level(src)
    
    if dry_run:
        result["ok"] = True
        result["line"] = f"[dry-run] {src.name} → {dst.name} (level {effective_level}, threads {threads})"
        return result
        
    t0 = time.perf_counter()
    try:
        # Using ZstdCompressor for compression
        cctx = zstd.ZstdCompressor(level=effective_level, threads=threads)
        data = src.read_bytes()
        compressed = cctx.compress(data)
        dst.write_bytes(compressed)
        
        elapsed_ms = (time.perf_counter() - t0) * 1000
        after = len(compressed)
        before = len(data)
        
        src.unlink()
        result["ok"] = True
        result["line"] = status_line(True, src.name, elapsed_ms, before, after)
        if verbose:
            result["msg"] = (
                f"  → {dst.name} ({human_size(before)} → {human_size(after)}, "
                f"level {effective_level}, {threads} threads)"
            )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        result["line"] = status_line(False, src.name, elapsed_ms, 0, 0)
        result["msg"] = f"  ERROR: {exc}"
        
    return result

def decompress_file(src: Path, dry_run: bool, verbose: bool) -> dict:
    """Decompress a single Zstandard file."""
    result = {"src": src, "ok": False, "line": "", "msg": ""}
    if src.suffix != ZSTD_EXT:
        result["line"] = f"[–] {src.name} (skipped — not a {ZSTD_EXT} file)"
        return result
        
    dst = src.with_suffix("")
    if dst.exists():
        result["line"] = f"[–] {src.name} (skipped — {dst.name} exists)"
        return result
        
    if dry_run:
        result["ok"] = True
        result["line"] = f"[dry-run] {src.name} → {dst.name}"
        return result
        
    t0 = time.perf_counter()
    try:
        dctx = zstd.ZstdDecompressor()
        data = src.read_bytes()
        decompressed = dctx.decompress(data)
        dst.write_bytes(decompressed)
        
        elapsed_ms = (time.perf_counter() - t0) * 1000
        after = len(decompressed)
        before = len(data)
        
        src.unlink()
        result["ok"] = True
        result["line"] = status_line(True, src.name, elapsed_ms, before, after)
        if verbose:
            result["msg"] = f"  → {dst.name} ({human_size(before)} → {human_size(after)})"
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        result["line"] = status_line(False, src.name, elapsed_ms, 0, 0)
        result["msg"] = f"  ERROR: {exc}"
        
    return result

def tar_subdir(subdir: Path, dry_run: bool, verbose: bool) -> Path | None:
    """Archive a subdirectory into a tar file."""
    tar_path = subdir.parent / f"{subdir.name}.tar"
    if dry_run:
        if verbose:
            logger.info(f"  [dry-run] would tar {subdir}/ → {tar_path.name}")
        return tar_path
        
    try:
        with tarfile.open(tar_path, "w") as tf:
            tf.add(subdir, arcname=subdir.name)
        if verbose:
            logger.info(f"  tarred {subdir.name}/ → {tar_path.name} ({human_size(tar_path.stat().st_size)})")
        return tar_path
    except Exception as exc:
        logger.error(f"  ERROR tarring {subdir}: {exc}")
        return None

def remove_subdir(subdir: Path, dry_run: bool, verbose: bool) -> None:
    """Remove a subdirectory recursively."""
    if dry_run:
        if verbose:
            logger.info(f"  [dry-run] would remove {subdir}/")
        return
        
    try:
        shutil.rmtree(subdir)
        if verbose:
            logger.info(f"  removed original dir: {subdir.name}/")
    except Exception as exc:
        logger.warning(f"  WARNING — could not remove {subdir}: {exc}")

def run_parallel(tasks: list[Path], worker_fn, extra_kwargs: dict) -> tuple[int, int]:
    """Execute tasks in parallel using ProcessPoolExecutor."""
    ok = err = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(worker_fn, path, **extra_kwargs): path for path in tasks}
        for fut in as_completed(futures):
            res = fut.result()
            logger.info(res["line"])
            if res.get("msg"):
                if res["ok"]:
                    logger.info(res["msg"])
                else:
                    logger.error(res["msg"])
            
            if res["ok"]:
                ok += 1
            else:
                err += 1
    return ok, err

def do_compress(root: Path, tar_subdirs: bool, dry_run: bool, verbose: bool, threads: int) -> None:
    """Orchestrate compression of a directory."""
    start = time.perf_counter()
    if tar_subdirs:
        subdirs = [p for p in root.iterdir() if p.is_dir() and p.name not in SKIP_DIRS]
        if verbose:
            logger.info(f"Tarring {len(subdirs)} subdirectory/ies …")
            
        tar_paths = []
        for sd in subdirs:
            tp = tar_subdir(sd, dry_run, verbose)
            if tp:
                tar_paths.append((sd, tp))
        
        tar_files = [tp for _, tp in tar_paths]
        if tar_files:
            if verbose:
                logger.info(f"Compressing {len(tar_files)} .tar archive(s) at level {LEVEL_LARGE} …")
            run_parallel(
                tar_files,
                compress_file,
                {"dry_run": dry_run, "verbose": verbose, "level": LEVEL_LARGE, "threads": threads},
            )
            
            compressed = {tp for tp in tar_files if tp.with_suffix(tp.suffix + ZSTD_EXT).exists() or dry_run}
            for sd, tp in tar_paths:
                if tp in compressed:
                    remove_subdir(sd, dry_run, verbose)
                    
        loose = [p for p in root.iterdir() if p.is_file() and p.suffix != ZSTD_EXT]
        if loose:
            if verbose:
                logger.info(f"Compressing {len(loose)} loose file(s) …")
            run_parallel(loose, compress_file, {"dry_run": dry_run, "verbose": verbose, "threads": threads})
    else:
        files = [p for p in root.rglob("*") if p.is_file() and p.suffix != ZSTD_EXT and not any(part in SKIP_DIRS for part in p.parts)]
        if not files:
            logger.info("No files to compress.")
            return
            
        if verbose:
            logger.info(f"Compressing {len(files)} file(s) with {WORKERS} processes × {threads} zstd threads each …")
        
        ok, err = run_parallel(files, compress_file, {"dry_run": dry_run, "verbose": verbose, "threads": threads})
        elapsed = time.perf_counter() - start
        logger.info(f"\nDone — {ok} compressed, {err} error(s) [{elapsed:.2f}s]")
        return
        
    elapsed = time.perf_counter() - start
    logger.info(f"\nDone [{elapsed:.2f}s]")

def do_decompress(root: Path, dry_run: bool, verbose: bool) -> None:
    """Orchestrate decompression of Zstandard files in a directory."""
    start = time.perf_counter()
    files = [p for p in root.rglob(f"*{ZSTD_EXT}") if p.is_file()]
    if not files:
        logger.info(f"No {ZSTD_EXT} files found.")
        return
        
    if verbose:
        logger.info(f"Decompressing {len(files)} file(s) with {WORKERS} workers …")
        
    ok, err = run_parallel(files, decompress_file, {"dry_run": dry_run, "verbose": verbose})
    elapsed = time.perf_counter() - start
    logger.info(f"\nDone — {ok} decompressed, {err} error(s) [{elapsed:.2f}s]")

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="zstder",
        description="Recursive Zstandard compression/decompression tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-c", "--compress", action="store_true", help="Compress files (default)")
    mode.add_argument("-d", "--decompress", action="store_true", help="Decompress files")
    
    parser.add_argument("-t", "--tar-subdirs-first", action="store_true", help="Tar subdirs before compressing.")
    parser.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_THREADS,
        help=f"zstd intra-file compression threads (default: {DEFAULT_THREADS}).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Do not modify files")
    parser.add_argument("directory", nargs="?", default=".", help="Root directory (default: current)")
    
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")
        
    compress = args.compress or not args.decompress
    
    if args.dry_run:
        logger.info("[dry-run mode — no files will be modified]")
        
    if args.verbose or args.dry_run:
        logger.info(f"Root    : {root}")
        logger.info(f"Mode    : {'compress' if compress else 'decompress'}")
        logger.info(f"Threads : {args.threads} (zstd) × {WORKERS} processes")
        logger.info("")
        
    if compress:
        do_compress(root, args.tar_subdirs_first, args.dry_run, args.verbose, args.threads)
    else:
        if args.tar_subdirs_first:
            logger.warning("Note: --tar-subdirs-first ignored during decompression.")
        do_decompress(root, args.dry_run, args.verbose)

if __name__ == "__main__":
    main()
