#!/data/data/com.termux/files/usr/bin/python
"""
zstd_compress.py — Recursive zstandard compression/decompression tool.

Strategy: Situation 2 — multiprocess files in parallel.
zstd supports native multithreading per file via its threads parameter,
so each worker process also leverages intra-file parallelism.
"""

import argparse
import multiprocessing
import os
import shutil
import sys
import tarfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import zstandard as zstd

# ── constants ────────────────────────────────────────────────────────────────
LARGE_FILE_THRESHOLD = 5 * 1024 * 1024  # 5 MB
LEVEL_DEFAULT = 19  # max practical level
LEVEL_LARGE = 9  # balanced for large files / tar
ZSTD_EXT = ".zst"
DEFAULT_THREADS = 4
WORKERS = max(1, multiprocessing.cpu_count())

# zstd tuning
ZSTD_WINDOW_LOG = 27  # 128 MB window — best ratio for level 19
ZSTD_OVERLAP_LOG = 6  # overlap between MT jobs (windowSize/8)


# ── helpers ──────────────────────────────────────────────────────────────────


def choose_level(path: Path) -> int:
    try:
        return LEVEL_LARGE if path.stat().st_size > LARGE_FILE_THRESHOLD else LEVEL_DEFAULT
    except OSError:
        return LEVEL_DEFAULT


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def ratio_str(before: int, after: int) -> str:
    """Return after/before as a percentage string, e.g. '34%'."""
    if before == 0:
        return "0%"
    return f"{after / before * 100:.0f}%"


def status_line(ok: bool, name: str, elapsed_ms: float, before: int, after: int) -> str:
    """Format: [✔] file.txt (324ms) 34%"""
    icon = "✔" if ok else "✘"
    return f"[{icon}] {name} ({elapsed_ms:.0f}ms) {ratio_str(before, after)}"


# ── single-file workers (run in child processes) ─────────────────────────────


def compress_file(
    src: Path, dry_run: bool, verbose: bool, level: int | None = None, threads: int = DEFAULT_THREADS
) -> dict:
    result = {"src": src, "ok": False, "line": "", "msg": ""}

    dst = src.with_suffix(src.suffix + ZSTD_EXT)
    if dst.exists():
        result["line"] = f"[–] {src.name} (skipped — {dst.name} exists)"
        return result

    effective_level = level if level is not None else choose_level(src)
    before = src.stat().st_size if not dry_run else 0

    if dry_run:
        result["ok"] = True
        result["line"] = f"[dry-run] {src.name} → {dst.name} (level {effective_level}, threads {threads})"
        return result

    t0 = time.perf_counter()
    try:
        params = zstd.ZstdCompressionParameters.from_level(
            effective_level,
            threads=threads,
            window_log=ZSTD_WINDOW_LOG,
            overlap_log=ZSTD_OVERLAP_LOG,
        )
        cctx = zstd.ZstdCompressor(compression_params=params)

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
                f"  → {dst.name} ({human(before)} → {human(after)}, level {effective_level}, {threads} threads)"
            )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        result["line"] = status_line(False, src.name, elapsed_ms, 0, 0)
        result["msg"] = f"  ERROR: {exc}"

    return result


def decompress_file(src: Path, dry_run: bool, verbose: bool, threads: int = DEFAULT_THREADS) -> dict:
    result = {"src": src, "ok": False, "line": "", "msg": ""}

    if src.suffix != ZSTD_EXT:
        result["line"] = f"[–] {src.name} (skipped — not a .zst file)"
        return result

    dst = src.with_suffix("")
    if dst.exists():
        result["line"] = f"[–] {src.name} (skipped — {dst.name} exists)"
        return result

    before = src.stat().st_size if not dry_run else 0

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
        # for decompression the ratio is inverted (after > before), still show it
        result["line"] = status_line(True, src.name, elapsed_ms, before, after)
        if verbose:
            result["msg"] = f"  → {dst.name} ({human(before)} → {human(after)})"
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        result["line"] = status_line(False, src.name, elapsed_ms, 0, 0)
        result["msg"] = f"  ERROR: {exc}"

    return result


# ── tar-subdirs helper ───────────────────────────────────────────────────────


def tar_subdir(subdir: Path, dry_run: bool, verbose: bool) -> Path | None:
    tar_path = subdir.parent / (subdir.name + ".tar")
    if dry_run:
        if verbose:
            print(f"  [dry-run] would tar {subdir}/ → {tar_path.name}")
        return tar_path
    try:
        with tarfile.open(tar_path, "w") as tf:
            tf.add(subdir, arcname=subdir.name)
        if verbose:
            print(f"  tarred {subdir.name}/ → {tar_path.name} ({human(tar_path.stat().st_size)})")
        return tar_path
    except Exception as exc:
        print(f"  ERROR tarring {subdir}: {exc}", file=sys.stderr)
        return None


def remove_subdir(subdir: Path, dry_run: bool, verbose: bool) -> None:
    if dry_run:
        if verbose:
            print(f"  [dry-run] would remove {subdir}/")
        return
    try:
        shutil.rmtree(subdir)
        if verbose:
            print(f"  removed original dir: {subdir.name}/")
    except Exception as exc:
        print(f"  WARNING — could not remove {subdir}: {exc}", file=sys.stderr)


# ── parallel dispatcher ───────────────────────────────────────────────────────


def run_parallel(tasks: list, worker_fn, extra_kwargs: dict) -> tuple[int, int]:
    ok = err = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(worker_fn, path, **extra_kwargs): path for path in tasks}
        for fut in as_completed(futures):
            res = fut.result()
            print(res["line"])
            if res.get("msg"):
                print(res["msg"], file=sys.stderr if not res["ok"] else sys.stdout)
            if res["ok"]:
                ok += 1
            else:
                err += 1
    return ok, err


# ── main operations ───────────────────────────────────────────────────────────


def do_compress(root: Path, tar_subdirs: bool, dry_run: bool, verbose: bool, threads: int) -> None:
    start = time.perf_counter()

    if tar_subdirs:
        subdirs = [p for p in root.iterdir() if p.is_dir()]
        if verbose:
            print(f"Taring {len(subdirs)} subdirectory/ies …")

        tar_paths = []
        for sd in subdirs:
            tp = tar_subdir(sd, dry_run, verbose)
            if tp:
                tar_paths.append((sd, tp))

        tar_files = [tp for _, tp in tar_paths]
        if tar_files:
            if verbose:
                print(f"Compressing {len(tar_files)} .tar archive(s) at level {LEVEL_LARGE} …")
            run_parallel(
                tar_files,
                compress_file,
                {"dry_run": dry_run, "verbose": verbose, "level": LEVEL_LARGE, "threads": threads},
            )
            compressed = {tp for tp in tar_files if (tp.with_suffix(tp.suffix + ZSTD_EXT)).exists() or dry_run}
            for sd, tp in tar_paths:
                if tp in compressed:
                    remove_subdir(sd, dry_run, verbose)

        loose = [p for p in root.iterdir() if p.is_file() and p.suffix != ZSTD_EXT]
        if loose:
            if verbose:
                print(f"Compressing {len(loose)} loose file(s) …")
            run_parallel(loose, compress_file, {"dry_run": dry_run, "verbose": verbose, "threads": threads})
    else:
        files = [p for p in root.rglob("*") if p.is_file() and p.suffix != ZSTD_EXT]
        if not files:
            print("No files to compress.")
            return
        if verbose:
            print(f"Compressing {len(files)} file(s) with {WORKERS} processes × {threads} zstd threads each …")
        ok, err = run_parallel(files, compress_file, {"dry_run": dry_run, "verbose": verbose, "threads": threads})
        elapsed = time.perf_counter() - start
        print(f"\nDone — {ok} compressed, {err} error(s) [{elapsed:.2f}s]")
        return

    elapsed = time.perf_counter() - start
    print(f"\nDone [{elapsed:.2f}s]")


def do_decompress(root: Path, dry_run: bool, verbose: bool, threads: int) -> None:
    start = time.perf_counter()
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix == ZSTD_EXT]
    if not files:
        print("No .zst files found.")
        return
    if verbose:
        print(f"Decompressing {len(files)} file(s) with {WORKERS} workers …")
    ok, err = run_parallel(files, decompress_file, {"dry_run": dry_run, "verbose": verbose, "threads": threads})
    elapsed = time.perf_counter() - start
    print(f"\nDone — {ok} decompressed, {err} error(s) [{elapsed:.2f}s]")


# ── CLI ───────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zstd_compress",
        description="Recursive zstandard compression / decompression.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("-c", "--compress", action="store_true")
    mode.add_argument("-d", "--decompress", action="store_true")
    p.add_argument("-t", "--tar-subdirs-first", action="store_true", help="Tar subdirs before compressing.")
    p.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_THREADS,
        help=f"zstd intra-file compression threads (default: {DEFAULT_THREADS}).",
    )
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("directory", nargs="?", default=".")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")

    compress = args.compress or (not args.decompress)

    if args.dry_run:
        print("[dry-run mode — no files will be modified]")
    if args.verbose or args.dry_run:
        print(f"Root    : {root}")
        print(f"Mode    : {'compress' if compress else 'decompress'}")
        print(f"Threads : {args.threads} (zstd) × {WORKERS} processes")
        print()

    if compress:
        do_compress(root, args.tar_subdirs_first, args.dry_run, args.verbose, args.threads)
    else:
        if args.tar_subdirs_first:
            print("Note: --tar-subdirs-first ignored during decompression.", file=sys.stderr)
        do_decompress(root, args.dry_run, args.verbose, args.threads)


if __name__ == "__main__":
    main()
