#!/data/data/com.termux/files/usr/bin/python

import bz2
import gzip
import hashlib
import lzma
import multiprocessing as mp
import shutil
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import brotli
import py7zr
import zstandard as zstd
from dh import compress as snappy_compress
from loguru import logger

try:
    import huffman as huffman_lib
except Exception:
    huffman_lib = None


@dataclass
class Result:
    algo: str
    input_path: str
    out_path: str
    out_size: int
    elapsed_s: float
    ok: bool
    error: Optional[str] = None


def human(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    x = float(n)
    for u in units:
        if x < 1024.0:
            return f"{x:.2f} {u}"
        x /= 1024.0
    return f"{x:.2f} PiB"


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def best_ext(algo: str) -> str:
    return {
        "brotli": ".br",
        "huffman": ".hf",
        "gz": ".gz",
        "bz2": ".bz2",
        "lzma": ".xz",
        "zip": ".zip",
        "snappy": ".snappy",
        "zstd": ".zst",
        "7z": ".7z",
    }.get(algo, f".{algo}")


def compress_7z(in_path: Path, out_path: Path) -> None:
    with py7zr.SevenZipFile(out_path, mode="w", filters=None) as z:
        z.write(in_path, arcname=in_path.name)


def compress_gz(in_path: Path, out_path: Path) -> None:
    with in_path.open("rb") as fin, gzip.open(out_path, "wb", compresslevel=9) as fout:
        shutil.copyfileobj(fin, fout, length=1024 * 1024)


def compress_bz2(in_path: Path, out_path: Path) -> None:
    with in_path.open("rb") as fin, bz2.open(out_path, "wb", compresslevel=9) as fout:
        shutil.copyfileobj(fin, fout, length=1024 * 1024)


def compress_lzma(in_path: Path, out_path: Path) -> None:
    with lzma.open(out_path, "wb", preset=9 | lzma.PRESET_EXTREME) as fout:
        with in_path.open("rb") as fin:
            shutil.copyfileobj(fin, fout, length=1024 * 1024)


def compress_zip(in_path: Path, out_path: Path) -> None:
    with zipfile.ZipFile(out_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(in_path, arcname=in_path.name)


def compress_brotli(in_path: Path, out_path: Path) -> None:
    data = in_path.read_bytes()
    out_path.write_bytes(brotli.compress(data, quality=11, lgwin=22))


def compress_huffman(in_path: Path, out_path: Path) -> None:
    if huffman_lib is None:
        raise RuntimeError("huffman library not available")
    data = in_path.read_bytes()
    if hasattr(huffman_lib, "compress"):
        out_path.write_bytes(huffman_lib.compress(data))
    elif hasattr(huffman_lib, "HuffmanCodec"):
        codec = huffman_lib.HuffmanCodec(data)
        out_path.write_bytes(codec.encode(data))
    else:
        raise RuntimeError("Unsupported huffman library API")


def compress_snappy(in_path: Path, out_path: Path) -> None:
    out_path.write_bytes(snappy_compress(in_path.read_bytes()))


def compress_zstd(in_path: Path, out_path: Path) -> None:
    cctx = zstd.ZstdCompressor(level=21)
    out_path.write_bytes(cctx.compress(in_path.read_bytes()))


ALGO_SINGLE: Dict[str, Tuple[str, Any]] = {
    "7z": ("7z", compress_7z),
    "gz": ("gz", compress_gz),
    "lzma": ("lzma", compress_lzma),
    "bz2": ("bz2", compress_bz2),
    "zip": ("zip", compress_zip),
    "brotli": ("brotli", compress_brotli),
    "huffman": ("huffman", compress_huffman),
    "snappy": ("snappy", compress_snappy),
    "zstd": ("zstd", compress_zstd),
}


def run_single(algo: str, in_path: Path, tmpdir: Path) -> Result:
    try:
        out_path = tmpdir / f"{in_path.name}{best_ext(algo)}"
        fn = ALGO_SINGLE[algo][1]
        t0 = time.perf_counter()
        fn(in_path, out_path)
        elapsed = time.perf_counter() - t0
        out_size = out_path.stat().st_size
        return Result(
            algo=algo, input_path=str(in_path), out_path=str(out_path), out_size=out_size, elapsed_s=elapsed, ok=True
        )
    except Exception as e:
        logger.exception(f"[{algo}] failed: {e}")
        return Result(
            algo=algo, input_path=str(in_path), out_path="", out_size=0, elapsed_s=0.0, ok=False, error=str(e)
        )


WORKER_ALGOS = {"gz", "bz2", "lzma", "zstd", "brotli", "snappy"}


def _chunk_compressor(algo: str):
    if algo == "gz":

        def f(chunk: bytes) -> bytes:
            import gzip
            import io

            out = io.BytesIO()
            with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=9) as g:
                g.write(chunk)
            return out.getvalue()

        return f
    if algo == "bz2":

        def f(chunk: bytes) -> bytes:
            import io

            out = io.BytesIO()
            with bz2.BZ2File(out, mode="wb", compresslevel=9) as b:
                b.write(chunk)
            return out.getvalue()

        return f
    if algo == "lzma":

        def f(chunk: bytes) -> bytes:
            import io

            out = io.BytesIO()
            with lzma.LZMAFile(out, mode="wb", preset=9 | lzma.PRESET_EXTREME) as l:
                l.write(chunk)
            return out.getvalue()

        return f
    if algo == "zstd":

        def f(chunk: bytes) -> bytes:
            return zstd.ZstdCompressor(level=22).compress(chunk)

        return f
    if algo == "brotli":

        def f(chunk: bytes) -> bytes:
            return brotli.compress(chunk, quality=11, lgwin=22)

        return f
    if algo == "snappy":

        def f(chunk: bytes) -> bytes:
            return snappy_compress(chunk)

        return f
    raise ValueError(algo)


def _worker(arg):
    algo, chunk = arg
    return _chunk_compressor(algo)(chunk)


def mp_compress_chunks(algo: str, in_path: Path, tmpdir: Path, chunk_size: int, processes: Optional[int]) -> Result:
    if algo not in WORKER_ALGOS:
        return Result(
            algo=f"mp_{algo}",
            input_path=str(in_path),
            out_path="",
            out_size=0,
            elapsed_s=0.0,
            ok=False,
            error="Chunk mode not supported",
        )
    try:
        out_path = tmpdir / f"{in_path.name}.mp_{algo}{best_ext(algo)}"
        t0 = time.perf_counter()
        chunks = []
        with in_path.open("rb") as f:
            while True:
                b = f.read(chunk_size)
                if not b:
                    break
                chunks.append(b)
        with mp.Pool(processes=processes or mp.cpu_count()) as pool:
            compressed_parts = pool.map(_worker, [(algo, c) for c in chunks])
        with out_path.open("wb") as fout:
            for part in compressed_parts:
                fout.write(part)
        elapsed = time.perf_counter() - t0
        out_size = out_path.stat().st_size
        return Result(
            algo=f"mp_{algo}",
            input_path=str(in_path),
            out_path=str(out_path),
            out_size=out_size,
            elapsed_s=elapsed,
            ok=True,
        )
    except Exception as e:
        logger.exception(f"[mp_{algo}] failed: {e}")
        return Result(
            algo=f"mp_{algo}", input_path=str(in_path), out_path="", out_size=0, elapsed_s=0.0, ok=False, error=str(e)
        )


def choose_best(results: List[Result]) -> Optional[Result]:
    ok = [r for r in results if r.ok and r.out_path]
    if not ok:
        return None
    ok.sort(key=lambda r: (r.out_size, r.elapsed_s))
    return ok[0]


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <filename>", file=sys.stderr)
        sys.exit(1)
    in_path = Path(sys.argv[1]).expanduser()
    if not in_path.exists() or not in_path.is_file():
        print(f"Error: file not found: {in_path}", file=sys.stderr)
        sys.exit(1)
    logger.info(f"Input: {in_path} ({human(in_path.stat().st_size)})")
    try:
        logger.info(f"SHA256(input)={file_sha256(in_path)}")
    except Exception:
        logger.warning("Could not compute SHA256")
    with tempfile.TemporaryDirectory(prefix="compress_bench_") as td:
        tmpdir = Path(td)
        single_algos = ["7z", "gz", "lzma", "bz2", "zip", "brotli", "huffman", "snappy", "zstd"]
        results_single: List[Result] = []
        logger.info("=== Single-process benchmark ===")
        for algo in single_algos:
            logger.info(f"Compressing {algo} ...")
            r = run_single(algo, in_path, tmpdir)
            results_single.append(r)
            if r.ok:
                logger.info(f"[{algo}] OK size={human(r.out_size)} time={r.elapsed_s:.4f}s out={Path(r.out_path).name}")
            else:
                logger.error(f"[{algo}] FAIL {r.error}")
        mp_algos = ["gz", "bz2", "lzma", "zstd", "brotli", "snappy"]
        chunk_size = 4 * 1024 * 1024
        processes = None
        logger.info("=== Multiprocessing chunk benchmark (reporting only) ===")
        mp_results: List[Result] = []
        for algo in mp_algos:
            logger.info(f"MP chunk compress {algo} (chunk_size={human(chunk_size)}) ...")
            r = mp_compress_chunks(algo, in_path, tmpdir, chunk_size=chunk_size, processes=processes)
            mp_results.append(r)
            if r.ok:
                logger.info(
                    f"[mp_{algo}] OK size={human(r.out_size)} time={r.elapsed_s:.4f}s out={Path(r.out_path).name}"
                )
            else:
                logger.error(f"[mp_{algo}] FAIL {r.error}")
        best_overall = choose_best(results_single + mp_results)
        if not best_overall:
            print("Could not determine best compressed output.", file=sys.stderr)
            sys.exit(3)
        print("\nSingle-process results:")
        ok_single = [r for r in results_single if r.ok]
        ok_single.sort(key=lambda r: (r.out_size, r.elapsed_s))
        print(f"{'Algo':<10} {'Size':>15} {'Time(s)':>12}")
        print("-" * 40)
        for r in ok_single:
            print(f"{r.algo:<10} {human(r.out_size):>15} {r.elapsed_s:>12.4f}")
        print(
            f"\nBest overall: {best_overall.algo} size={human(best_overall.out_size)} time={best_overall.elapsed_s:.4f}s"
        )
        if best_overall.algo.startswith("mp_"):
            base_algo = best_overall.algo[len("mp_") :]
        else:
            base_algo = best_overall.algo
        out_final = in_path.with_name(in_path.name + best_ext(base_algo))
        shutil.copy2(best_overall.out_path, out_final)
        logger.info(f"Saved best output to: {out_final}")


if __name__ == "__main__":
    main()
