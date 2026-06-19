#!/data/data/com.termux/files/usr/bin/python
"""
Smart Archiver - Automatically chooses best compression algorithm based on file type
and supports parallel compression for multiple files.
"""

import os
import sys
import tarfile
import tempfile
from pathlib import Path
import time
from io import BytesIO
import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from datetime import datetime

try:
    import zstandard as zstd
except ImportError:
    zstd = None
try:
    import brotli
except ImportError:
    brotli = None
try:
    import lzma
except ImportError:
    lzma = None
try:
    import gzip
except ImportError:
    gzip = None
try:
    import bz2
except ImportError:
    bz2 = None
try:
    import lz4.frame
except ImportError:
    lz4 = None
EXTENSION_MAP = {
    ".txt": {"algo": "brotli", "level": 11},
    ".log": {"algo": "brotli", "level": 11},
    ".csv": {"algo": "brotli", "level": 11},
    ".json": {"algo": "brotli", "level": 11},
    ".xml": {"algo": "brotli", "level": 11},
    ".html": {"algo": "brotli", "level": 11},
    ".css": {"algo": "brotli", "level": 11},
    ".js": {"algo": "brotli", "level": 11},
    ".md": {"algo": "brotli", "level": 11},
    ".yaml": {"algo": "brotli", "level": 11},
    ".yml": {"algo": "brotli", "level": 11},
    ".sql": {"algo": "brotli", "level": 11},
    ".py": {"algo": "zstd", "level": 19},
    ".c": {"algo": "zstd", "level": 19},
    ".cpp": {"algo": "zstd", "level": 19},
    ".h": {"algo": "zstd", "level": 19},
    ".java": {"algo": "zstd", "level": 19},
    ".go": {"algo": "zstd", "level": 19},
    ".rs": {"algo": "zstd", "level": 19},
    ".rb": {"algo": "zstd", "level": 19},
    ".php": {"algo": "zstd", "level": 19},
    ".swift": {"algo": "zstd", "level": 19},
    ".kt": {"algo": "zstd", "level": 19},
    ".zip": {"algo": "lz4", "level": 1},
    ".gz": {"algo": "lz4", "level": 1},
    ".bz2": {"algo": "lz4", "level": 1},
    ".xz": {"algo": "lz4", "level": 1},
    ".7z": {"algo": "lz4", "level": 1},
    ".rar": {"algo": "lz4", "level": 1},
    ".zst": {"algo": "lz4", "level": 1},
    ".br": {"algo": "lz4", "level": 1},
    ".jpg": {"algo": "lz4", "level": 1},
    ".jpeg": {"algo": "lz4", "level": 1},
    ".png": {"algo": "lz4", "level": 1},
    ".gif": {"algo": "lz4", "level": 1},
    ".bmp": {"algo": "zstd", "level": 19},
    ".webp": {"algo": "lz4", "level": 1},
    ".mp4": {"algo": "lz4", "level": 1},
    ".avi": {"algo": "lz4", "level": 1},
    ".mkv": {"algo": "lz4", "level": 1},
    ".mov": {"algo": "lz4", "level": 1},
    ".wmv": {"algo": "lz4", "level": 1},
    ".flv": {"algo": "lz4", "level": 1},
    ".mp3": {"algo": "lz4", "level": 1},
    ".flac": {"algo": "lz4", "level": 1},
    ".wav": {"algo": "zstd", "level": 19},
    ".aac": {"algo": "lz4", "level": 1},
    ".ogg": {"algo": "lz4", "level": 1},
    ".exe": {"algo": "zstd", "level": 19},
    ".dll": {"algo": "zstd", "level": 19},
    ".so": {"algo": "zstd", "level": 19},
    ".bin": {"algo": "zstd", "level": 19},
    ".pdf": {"algo": "zstd", "level": 19},
    ".docx": {"algo": "lz4", "level": 1},
    ".xlsx": {"algo": "lz4", "level": 1},
    ".pptx": {"algo": "lz4", "level": 1},
    ".epub": {"algo": "lz4", "level": 1},
    ".tar": {"algo": "zstd", "level": 19},
}
DEFAULT_SETTINGS = {
    "small_text": {"algo": "brotli", "level": 11},
    "large_text": {"algo": "zstd", "level": 19},
    "small_binary": {"algo": "zstd", "level": 19},
    "large_binary": {"algo": "zstd", "level": 21},
    "already_compressed": {"algo": "lz4", "level": 1},
}


def compress_zstd(data, level):
    compressor = zstd.ZstdCompressor(level=level)
    return compressor.compress(data)


def compress_brotli_standard(data, level):
    return brotli.compress(data, quality=level)


def compress_brotli_streaming(data, level, chunk_size=512 * 1024) -> bytes:
    compressor = brotli.Compressor(quality=level)
    result_parts = []
    for i in range(0, len(data), chunk_size):
        chunk = data[i : i + chunk_size]
        result_parts.append(compressor.process(chunk))
    result_parts.append(compressor.finish())
    return b"".join(result_parts)


def compress_lzma(data, level):
    return lzma.compress(data, preset=level)


def compress_gzip(data, level) -> bytes:
    out = BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=level) as gz:
        gz.write(data)
    return out.getvalue()


def compress_bz2(data, level):
    return bz2.compress(data, compresslevel=level)


def compress_lz4(data, level):
    return lz4.frame.compress(data, compression_level=level)


def compress_data(data: bytes, algo: int | str, level, is_large: bool = False):
    if algo == "zstd":
        return compress_zstd(data, level)
    elif algo == "brotli":
        if is_large:
            return compress_brotli_streaming(data, level)
        else:
            return compress_brotli_standard(data, level)
    elif algo == "lzma":
        return compress_lzma(data, level)
    elif algo == "gzip":
        return compress_gzip(data, level)
    elif algo == "bz2":
        return compress_bz2(data, level)
    elif algo == "lz4":
        return compress_lz4(data, level)
    else:
        raise ValueError(f"Unknown algorithm: {algo}")


def is_already_compressed(data, sample_size=4096) -> bool:
    if len(data) < 4:
        return False
    magic_bytes = {
        b"\x1f\x8b": "gzip",
        b"BZh": "bzip2",
        b"\xfd7zXZ": "xz",
        b"PK\x03\x04": "zip",
        b"(\xb5/\xfd": "zstd",
        b"\x89PNG\r\n\x1a\n": "png",
        b"\xff\xd8\xff": "jpeg",
        b"Rar!": "rar",
        b"7z\xbc\xaf'\x1c": "7z",
    }
    for magic, name in magic_bytes.items():
        if data.startswith(magic):
            return True
    return False


def choose_algorithm(file_path: Path, data: bytes | None = None, file_size: int | None = None) -> dict[str, int | str]:
    ext = Path(file_path).suffix.lower()
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]
    if file_size is None and data is not None:
        file_size = len(data)
    elif file_size is None:
        file_size = Path(file_path).stat().st_size
    if data is not None and is_already_compressed(data):
        return DEFAULT_SETTINGS["already_compressed"]
    is_text = False
    if data is not None:
        sample = data[: min(8192, len(data))]
        if b"\x00" not in sample:
            printable = sum(32 <= b <= 126 or b in (9, 10, 13) for b in sample)
            is_text = printable / len(sample) > 0.8
    if is_text:
        if file_size < 10 * 1024 * 1024:
            return DEFAULT_SETTINGS["small_text"]
        else:
            return DEFAULT_SETTINGS["large_text"]
    elif file_size < 10 * 1024 * 1024:
        return DEFAULT_SETTINGS["small_binary"]
    elif file_size > 100 * 1024 * 1024:
        return DEFAULT_SETTINGS["large_binary"]
    else:
        return DEFAULT_SETTINGS["small_binary"]


def compress_single_file(file_path, output_path=None, remove_original: bool = False, verbose: bool = False):
    start_time = time.time()
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        settings = choose_algorithm(file_path, data)
        algo = settings["algo"]
        level = settings["level"]
        is_large = len(data) > 50 * 1024 * 1024
        compressed_data = compress_data(data, algo, level, is_large)
        if output_path is None:
            output_path = str(file_path) + f".{algo}"
        elif output_path.endswith("/") or output_path.endswith("\\"):
            output_path = Path(output_path) / (Path(file_path).name + f".{algo}")
        else:
            output_path = Path(output_path)
        with open(output_path, "wb") as f:
            f.write(compressed_data)
        if remove_original:
            os.remove(file_path)
        elapsed = time.time() - start_time
        original_size = len(data)
        compressed_size = len(compressed_data)
        ratio = compressed_size / original_size * 100
        if verbose:
            print(
                f"✓ {Path(file_path).name}: {algo.upper()}:{level} {original_size:,d} → {compressed_size:,d} bytes ({ratio:.1f}%) in {elapsed:.2f}s"
            )
        return {
            "file": str(file_path),
            "output": str(output_path),
            "algorithm": algo,
            "level": level,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "ratio": ratio,
            "time": elapsed,
            "success": True,
        }
    except Exception as e:
        if verbose:
            print(f"✗ Failed to compress {file_path}: {e}")
        return {"file": str(file_path), "success": False, "error": str(e)}


def compress_multiple_files(file_paths, output_dir=None, max_workers=None, remove_original=False, verbose=False):
    if max_workers is None:
        max_workers = multiprocessing.cpu_count()
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for file_path in file_paths:
            output_path = Path(output_dir) / (Path(file_path).name + ".compressed") if output_dir else None
            future = executor.submit(compress_single_file, file_path, output_path, remove_original, verbose)
            futures[future] = file_path
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if verbose and result["success"]:
                file_name = Path(result["file"]).name
                print(f"  Completed: {file_name} ({result['algorithm']})")
    return results


def create_tar_archive(source_dir, output_path=None, compression="auto", level=None, parallel=False, max_workers=None):
    start_time = time.time()
    source_dir = Path(source_dir)
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{source_dir.name}_{timestamp}.tar"
    tar_path = Path(str(output_path).replace(".gz", "").replace(".xz", "").replace(".zst", "").replace(".br", ""))
    if compression != "none" and compression != "auto":
        tar_path = tar_path.with_suffix("")
    print(f"Creating archive from {source_dir}...")
    file_count = 0
    total_size = 0
    with tarfile.open(tar_path, "w") as tar:
        for item in source_dir.rglob("*"):
            if item.is_file() and not item.is_symlink():
                tar.add(item, arcname=item.relative_to(source_dir))
                file_count += 1
                total_size += item.stat().st_size
                if file_count % 1000 == 0:
                    print(f"  Added {file_count} files...")
    print(f"\nArchived {file_count} files ({total_size / 1024 / 1024:.2f} MB)")
    if compression != "none":
        with open(tar_path, "rb") as f:
            tar_data = f.read()
        if compression == "auto":
            settings = choose_algorithm(tar_path, tar_data, total_size)
            algo = settings["algo"]
            level = settings["level"]
        elif compression in ["zstd", "brotli", "lz4", "lzma", "gzip", "bz2"]:
            algo = compression
            level = level or (11 if algo == "brotli" else 19 if algo == "zstd" else 9)
        else:
            raise ValueError(f"Unsupported compression: {compression}")
        print(f"Compressing with {algo.upper()} (level {level})...")
        is_large = len(tar_data) > 50 * 1024 * 1024
        compressed_data = compress_data(tar_data, algo, level, is_large)
        compressed_path = Path(f"{tar_path}.{algo}")
        with open(compressed_path, "wb") as f:
            f.write(compressed_data)
        os.remove(tar_path)
        final_path = compressed_path
        elapsed = time.time() - start_time
        compressed_size = len(compressed_data)
        ratio = compressed_size / total_size * 100
        print(f"\n✓ Archive created: {final_path}")
        print(f"  Size: {compressed_size / 1024 / 1024:.2f} MB ({ratio:.1f}% of original)")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Algorithm: {algo.upper()} level {level}")
        return final_path, {
            "file_count": file_count,
            "original_size": total_size,
            "compressed_size": compressed_size,
            "ratio": ratio,
            "time": elapsed,
            "algorithm": algo,
            "level": level,
        }
    else:
        elapsed = time.time() - start_time
        print(f"\n✓ Archive created: {tar_path}")
        print(f"  Size: {total_size / 1024 / 1024:.2f} MB")
        print(f"  Time: {elapsed:.2f}s")
        return tar_path, {"file_count": file_count, "original_size": total_size, "time": elapsed}


def decompress_file(compressed_path, output_dir=None, verbose: bool = False):
    compressed_path = Path(compressed_path)
    ext = compressed_path.suffix.lower()
    algo_map = {
        ".zstd": "zstd",
        ".zst": "zstd",
        ".br": "brotli",
        ".lz4": "lz4",
        ".xz": "lzma",
        ".gz": "gzip",
        ".bz2": "bz2",
    }
    algo = algo_map.get(ext)
    if not algo:
        raise ValueError(f"Unknown compression format: {ext}")
    with open(compressed_path, "rb") as f:
        compressed_data = f.read()
    if algo == "zstd":
        decompressor = zstd.ZstdDecompressor()
        data = decompressor.decompress(compressed_data)
    elif algo == "brotli":
        data = brotli.decompress(compressed_data)
    elif algo == "lz4":
        data = lz4.frame.decompress(compressed_data)
    elif algo == "lzma":
        data = lzma.decompress(compressed_data)
    elif algo == "gzip":
        with gzip.GzipFile(fileobj=BytesIO(compressed_data)) as gz:
            data = gz.read()
    elif algo == "bz2":
        data = bz2.decompress(compressed_data)
    else:
        raise ValueError(f"Decompression not implemented for {algo}")
    if output_dir:
        output_path = Path(output_dir) / compressed_path.stem
    else:
        output_path = compressed_path.with_suffix("")
        if output_path.suffix in [".tar"]:
            output_path = output_path.with_suffix("")
    with open(output_path, "wb") as f:
        f.write(data)
    if output_path.suffix == ".tar":
        import tarfile

        extract_dir = output_dir or output_path.parent / output_path.stem
        extract_dir.mkdir(exist_ok=True)
        with tarfile.open(output_path, "r") as tar:
            tar.extractall(extract_dir)
        os.remove(output_path)
        if verbose:
            print(f"✓ Extracted to: {extract_dir}")
        return extract_dir
    if verbose:
        print(f"✓ Decompressed to: {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smart Archiver - Automatically chooses best compression algorithm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compress a single file (auto-detects best algorithm)
  python smart_archiver.py compress document.txt
  
  # Compress multiple files in parallel
  python smart_archiver.py compress *.log --parallel --output-dir compressed/
  
  # Create compressed archive of a directory
  python smart_archiver.py archive myfolder/ --compression auto
  
  # Force specific compression algorithm
  python smart_archiver.py archive myfolder/ --compression zstd --level 22
  
  # Decompress a file
  python smart_archiver.py decompress document.txt.zstd
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    compress_parser = subparsers.add_parser("compress", help="Compress files")
    compress_parser.add_argument("files", nargs="+", help="Files to compress")
    compress_parser.add_argument("-o", "--output-dir", help="Output directory")
    compress_parser.add_argument("-p", "--parallel", action="store_true", help="Enable parallel compression")
    compress_parser.add_argument("-j", "--jobs", type=int, help="Number of parallel jobs (default: CPU count)")
    compress_parser.add_argument("--remove", action="store_true", help="Remove original files after compression")
    compress_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    archive_parser = subparsers.add_parser("archive", help="Create compressed archive")
    archive_parser.add_argument("directory", help="Directory to archive")
    archive_parser.add_argument("-o", "--output", help="Output file path")
    archive_parser.add_argument(
        "-c",
        "--compression",
        default="auto",
        choices=["auto", "zstd", "brotli", "lz4", "lzma", "gzip", "bz2", "none"],
        help="Compression algorithm (default: auto)",
    )
    archive_parser.add_argument("-l", "--level", type=int, help="Compression level (algorithm-specific)")
    archive_parser.add_argument("--parallel", action="store_true", help="Use parallel processing for file addition")
    archive_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    decompress_parser = subparsers.add_parser("decompress", help="Decompress files")
    decompress_parser.add_argument("files", nargs="+", help="Files to decompress")
    decompress_parser.add_argument("-o", "--output-dir", help="Output directory")
    decompress_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    benchmark_parser = subparsers.add_parser("benchmark", help="Benchmark different algorithms")
    benchmark_parser.add_argument("input", help="Input file or directory")
    benchmark_parser.add_argument("-o", "--output", help="Output JSON file for results")
    benchmark_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    missing = []
    if not zstd:
        missing.append("zstandard")
    if not brotli:
        missing.append("brotli")
    if missing:
        print(f"Warning: Missing optional libraries: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
        print("Some algorithms will not be available.\n")
    if args.command == "compress":
        files = []
        for pattern in args.files:
            files.extend(Path().glob(pattern))
        if not files:
            print(f"Error: No files found matching {args.files}")
            sys.exit(1)
        if args.parallel and len(files) > 1:
            results = compress_multiple_files(
                files,
                output_dir=args.output_dir,
                max_workers=args.jobs,
                remove_original=args.remove,
                verbose=args.verbose,
            )
            successful = sum(1 for r in results if r["success"])
            failed = len(results) - successful
            total_original = sum(r.get("original_size", 0) for r in results if r["success"])
            total_compressed = sum(r.get("compressed_size", 0) for r in results if r["success"])
            print(f"\n{'=' * 60}")
            print(f"COMPRESSION SUMMARY")
            print(f"  Successful: {successful}/{len(results)} files")
            if failed:
                print(f"  Failed: {failed} files")
            if successful:
                print(f"  Total size: {total_original / 1024 / 1024:.2f} MB → {total_compressed / 1024 / 1024:.2f} MB")
                print(f"  Overall ratio: {total_compressed / total_original * 100:.1f}%")
        else:
            for file_path in files:
                compress_single_file(file_path, args.output_dir, args.remove, args.verbose)
    elif args.command == "archive":
        create_tar_archive(
            args.directory,
            output_path=args.output,
            compression=args.compression,
            level=args.level,
            parallel=args.parallel,
            max_workers=args.jobs,
        )
    elif args.command == "decompress":
        for file_path in args.files:
            decompress_file(file_path, args.output_dir, args.verbose)
    elif args.command == "benchmark":
        from hybrid_compression_benchmark import benchmark_hybrid

        input_path = Path(args.input)
        if input_path.is_dir():
            with tempfile.TemporaryDirectory() as tmpdir:
                tar_path = Path(tmpdir) / "data.tar"
                with tarfile.open(tar_path, "w") as tar:
                    for item in input_path.rglob("*"):
                        if item.is_file():
                            tar.add(item, arcname=item.relative_to(input_path))
                data = tar_path.read_bytes()
                results = benchmark_hybrid(data, len(data))
                if args.output:
                    serializable = {}
                    for name, info in results.items():
                        serializable[name] = {k: v for k, v in info.items() if isinstance(v, (int, float, str))}
                    with open(args.output, "w") as f:
                        json.dump(serializable, f, indent=2)
                    print(f"\nResults saved to {args.output}")
        else:
            with open(input_path, "rb") as f:
                data = f.read()
            results = benchmark_hybrid(data, len(data))


if __name__ == "__main__":
    main()
