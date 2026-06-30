#!/data/data/com.termux/files/usr/bin/python


import bz2
import lzma
import os
import sys
import tarfile
import time
from collections import namedtuple
from pathlib import Path
import blosc
import brotli
import lz4.frame
import py7zr
import zstandard as zstd

CompressionResult = namedtuple("CompressionResult", ["name", "size", "ratio", "time", "path"])


def compress_brotli(data):
    return brotli.compress(data, quality=11)


def compress_zstd(data) -> bytes:
    cctx = zstd.ZstdCompressor(level=21)
    return cctx.compress(data)


def compress_xz(data) -> bytes:
    return lzma.compress(data, preset=9, format=lzma.FORMAT_XZ)


def compress_bz2(data) -> bytes:
    return bz2.compress(data, compresslevel=9)


def compress_gzip(data) -> bytes:
    import gzip

    return gzip.compress(data, compresslevel=9)


def compress_lz4(data):
    ctx = lz4.frame.create_compression_context(lz4.frame.COMPRESSIONLEVEL_MAX)
    return lz4.frame.compress(data, compression_context=ctx)


def compress_blosc(data):
    return blosc.compress(data, codec=blosc.Codec.zstd, clevel=9)


def compress_py7zr(input_path: str, output_path: str) -> None:
    with py7zr.SevenZipFile(output_path, "w") as archive:
        archive.write(input_path, arcname=Path(input_path).name)


def prepare_input(target_path: str) -> tuple[bytes, str]:
    target = Path(target_path)
    if target.is_file():
        with open(target, "rb") as f:
            return f.read(), target.name
    elif target.is_dir():
        tar_path = f"{target.name}.tar"
        with tarfile.open(tar_path, "w") as tar:
            tar.add(target, arcname=target.name)
        with open(tar_path, "rb") as f:
            data = f.read()
        os.remove(tar_path)
        return data, f"{target.name}.tar"
    else:
        raise ValueError(f"{target_path} is neither file nor directory")


def compress_all(data: bytes, base_name: str, output_dir="."):
    results = []
    original_size = len(data)
    compressors = [
        ("brotli", lambda d: compress_brotli(d), ".br"),
        ("zstd", lambda d: compress_zstd(d), ".zst"),
        ("xz", lambda d: compress_xz(d), ".xz"),
        ("bz2", lambda d: compress_bz2(d), ".bz2"),
        ("gzip", lambda d: compress_gzip(d), ".gz"),
        ("lz4", lambda d: compress_lz4(d), ".lz4"),
        ("blosc", lambda d: compress_blosc(d), ".blosc"),
    ]
    for name, compress_func, ext in compressors:
        output_path = os.path.join(output_dir, f"{base_name}{ext}")
        try:
            start = time.time()
            compressed = compress_func(data)
            elapsed = time.time() - start
            with open(output_path, "wb") as f:
                f.write(compressed)
            comp_size = len(compressed)
            ratio = comp_size / original_size
            results.append(CompressionResult(name=name, size=comp_size, ratio=ratio, time=elapsed, path=output_path))
            print(f"✓ {name:10} | Size: {comp_size:12,} | Ratio: {ratio:.4f} | Time: {elapsed:.3f}s")
        except Exception as e:
            print(f"✗ {name:10} | Error: {e}")
            if os.path.exists(output_path):
                os.remove(output_path)
    try:
        output_path = os.path.join(output_dir, f"{base_name}.7z")
        start = time.time()
        temp_file = f"_temp_{base_name}"
        with open(temp_file, "wb") as f:
            f.write(data)
        compress_py7zr(temp_file, output_path)
        elapsed = time.time() - start
        comp_size = os.path.getsize(output_path)
        ratio = comp_size / original_size
        results.append(CompressionResult(name="7z", size=comp_size, ratio=ratio, time=elapsed, path=output_path))
        print(f"✓ {'7z':10} | Size: {comp_size:12,} | Ratio: {ratio:.4f} | Time: {elapsed:.3f}s")
        os.remove(temp_file)
    except Exception as e:
        print(f"✗ {'7z':10} | Error: {e}")
    return sorted(results, key=lambda x: x.ratio)


def report_results(results, original_size: int) -> None:
    print("\n" + "=" * 70)
    print("TOP 3 COMPRESSION RESULTS")
    print("=" * 70)
    for i, result in enumerate(results[:3], 1):
        saved = original_size - result.size
        print(f"{i}. {result.name:10} | Size: {result.size:12,} | Ratio: {result.ratio:.4f} | Saved: {saved:12,} bytes")
    best = results[0]
    print(f"\n✓ Keeping best: {best.name} ({best.path})")
    for result in results[1:]:
        try:
            os.remove(result.path)
            print(f"✗ Deleted: {result.name}")
        except Exception as e:
            print(f"⚠ Failed to delete {result.name}: {e}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python script.py <file_or_directory>")
        sys.exit(1)
    target = sys.argv[1]
    if not os.path.exists(target):
        print(f"Error: {target} not found")
        sys.exit(1)
    print(f"📦 Compressing: {target}\n")
    try:
        data, base_name = prepare_input(target)
        original_size = len(data)
        print(f"Original size: {original_size:,} bytes\n")
        print("COMPRESSION PROGRESS:")
        print("-" * 70)
        results = compress_all(data, base_name)
        report_results(results, original_size)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
