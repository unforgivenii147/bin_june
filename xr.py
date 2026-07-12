#!/data/data/com.termux/files/usr/bin/env python


import argparse
import asyncio
import mmap
import shutil
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
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
import bz2
import gzip
import lzma

MAX_WORKERS = 4
CHUNK_SIZE = 524288
COMPRESSORS = {
    "zstd": {
        "ext": ".zst",
        "tar_ext": ".tar.zst",
        "available": HAS_ZSTD,
        "compress": None,
        "decompress": None,
        "settings": {"level": 22, "threads": 4},
    },
    "brotli": {
        "ext": ".br",
        "tar_ext": ".tar.br",
        "available": HAS_BROTLI,
        "compress": None,
        "decompress": None,
        "settings": {"quality": 11, "lgwin": 24},
    },
    "xz": {
        "ext": ".xz",
        "tar_ext": ".tar.xz",
        "available": True,
        "compress": None,
        "decompress": None,
        "settings": {"preset": 9},
    },
    "zstd": {
        "ext": ".zst",
        "tar_ext": ".tar.zst",
        "available": HAS_ZSTD,
        "compress": None,
        "decompress": None,
        "settings": {"level": 22},
    },
    "py7zr": {
        "ext": ".7z",
        "tar_ext": ".7z",
        "available": HAS_PY7ZR,
        "compress": None,
        "decompress": None,
        "settings": {
            "filters": [{"id": py7zr.FILTER_LZMA2, "preset": 9}],
            "dictionary_size": 256 * 1024 * 1024,
            "solid": True,
        },
    },
    "gzip": {
        "ext": ".gz",
        "tar_ext": ".tar.gz",
        "available": True,
        "compress": None,
        "decompress": None,
        "settings": {"compresslevel": 9},
    },
    "bz2": {
        "ext": ".bz2",
        "tar_ext": ".tar.bz2",
        "available": True,
        "compress": None,
        "decompress": None,
        "settings": {"compresslevel": 9},
    },
    "lz4": {
        "ext": ".lz4",
        "tar_ext": ".tar.lz4",
        "available": HAS_LZ4,
        "compress": None,
        "decompress": None,
        "settings": {"compression_level": 9, "mode": "high_compression", "acceleration": 1},
    },
}


def setup_compressors() -> None:
    if HAS_ZSTD:
        COMPRESSORS["zstd"]["compress"] = lambda data: zstd.ZstdCompressor(
            level=COMPRESSORS["zstd"]["settings"]["level"], threads=1
        ).compress(data)
        COMPRESSORS["zstd"]["decompress"] = zstd.decompress
    if HAS_BROTLI:
        COMPRESSORS["brotli"]["compress"] = lambda data: brotli.compress(
            data, quality=COMPRESSORS["brotli"]["settings"]["quality"], lgwin=COMPRESSORS["brotli"]["settings"]["lgwin"]
        )
        COMPRESSORS["brotli"]["decompress"] = brotli.decompress
    COMPRESSORS["xz"]["compress"] = lambda data: lzma.compress(data, preset=COMPRESSORS["xz"]["settings"]["preset"])
    COMPRESSORS["xz"]["decompress"] = lzma.decompress
    COMPRESSORS["gzip"]["compress"] = lambda data: gzip.compress(
        data, compresslevel=COMPRESSORS["gzip"]["settings"]["compresslevel"]
    )
    COMPRESSORS["gzip"]["decompress"] = gzip.decompress
    COMPRESSORS["bz2"]["compress"] = lambda data: bz2.compress(
        data, compresslevel=COMPRESSORS["bz2"]["settings"]["compresslevel"]
    )
    COMPRESSORS["bz2"]["decompress"] = bz2.decompress
    if HAS_LZ4:
        COMPRESSORS["lz4"]["compress"] = lambda data: lz4.frame.compress(
            data,
            compression_level=COMPRESSORS["lz4"]["settings"]["compression_level"],
            mode=COMPRESSORS["lz4"]["settings"]["mode"],
            acceleration=COMPRESSORS["lz4"]["settings"]["acceleration"],
            content_checksum=True,
            block_size=lz4.frame.BLOCKSIZE_MAX,
            block_linked=True,
        )
        COMPRESSORS["lz4"]["decompress"] = lz4.frame.decompress
    if HAS_PY7ZR:
        COMPRESSORS["py7zr"]["compress"] = None
        COMPRESSORS["py7zr"]["decompress"] = None


def compress_with_py7zr(data: bytes) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".7z") as tmp:
        tmp_path = Path(tmp.name)
    try:
        with py7zr.SevenZipFile(
            tmp_path,
            mode="w",
            filters=COMPRESSORS["py7zr"]["settings"]["filters"],
            dictionary_size=COMPRESSORS["py7zr"]["settings"]["dictionary_size"],
            solid=COMPRESSORS["py7zr"]["settings"]["solid"],
        ) as sevenz:
            with tempfile.NamedTemporaryFile(delete=False) as data_tmp:
                data_tmp.write(data)
                data_tmp.flush()
                sevenz.write(Path(data_tmp.name), arcname="data")
                Path(data_tmp.name).unlink()
        compressed = tmp_path.read_bytes()
        return compressed
    finally:
        tmp_path.unlink()


def decompress_with_py7zr(data: bytes) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".7z") as tmp:
        tmp_path = Path(tmp.name)
        tmp_path.write_bytes(data)
    try:
        with py7zr.SevenZipFile(tmp_path, mode="r") as sevenz:
            extract_dir = tempfile.mkdtemp()
            sevenz.extractall(path=extract_dir)
            extracted_file = Path(extract_dir) / "data"
            if extracted_file.exists():
                result = extracted_file.read_bytes()
            else:
                files = list(Path(extract_dir).rglob("*"))
                if files:
                    result = files[0].read_bytes()
                else:
                    raise Exception("No file extracted")
            shutil.rmtree(extract_dir)
            return result
    finally:
        tmp_path.unlink()


def fsz(size: float) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if abs(size) < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PiB"


def compress_in_memory(infile: Path, outfile: Path, compressor: str) -> bool:
    try:
        data = infile.read_bytes()
        if not data:
            return False
        if compressor == "py7zr":
            compressed = compress_with_py7zr(data)
        else:
            compressed = COMPRESSORS[compressor]["compress"](data)
        outfile.write_bytes(compressed)
        return True
    except Exception as e:
        print(f"Memory compression failed for {infile.name}: {e}")
        return False


def compress_chunk(data: bytes, compressor: str) -> bytes:
    if compressor == "py7zr":
        return compress_with_py7zr(data)
    else:
        return COMPRESSORS[compressor]["compress"](data)


def compress_chunked(in_path: Path, out_path: Path, file_size: int, compressor: str) -> bool:
    try:
        chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        with (
            out_path.open("wb", buffering=1024 * 1024) as fout,
            in_path.open("rb") as fin,
            mmap.mmap(fin.fileno(), length=0, access=mmap.ACCESS_READ) as mm,
        ):
            chunks = (mm[i * CHUNK_SIZE : min((i + 1) * CHUNK_SIZE, file_size)] for i in range(chunk_count))
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(compress_chunk, chunk, compressor): i for i, chunk in enumerate(chunks)}
                results = [None] * chunk_count
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        results[idx] = future.result()
                    except Exception as e:
                        print(f"Chunk {idx} compression failed: {e}")
                        return False
                for compressed_chunk in results:
                    if compressed_chunk:
                        fout.write(compressed_chunk)
                    else:
                        return False
            return True
    except Exception as e:
        print(f"Chunked compression failed for {in_path.name}: {e}")
        return False


def create_tar_archive(source_dir: Path, output_path: Path) -> bool:
    try:
        with tarfile.open(output_path, "w") as tar:
            for item in source_dir.rglob("*"):
                if item.is_file():
                    arcname = item.relative_to(source_dir.parent)
                    tar.add(item, arcname=arcname)
        return True
    except Exception as e:
        print(f"  Failed to create tar archive: {e}")
        return False


def compress_tar_archive(tar_path: Path, out_path: Path, compressor: str) -> bool:
    try:
        tar_size = tar_path.stat().st_size
        if tar_size < CHUNK_SIZE:
            success = compress_in_memory(tar_path, out_path, compressor)
        else:
            success = compress_chunked(tar_path, out_path, tar_size, compressor)
        if success and out_path.exists():
            compressed_size = out_path.stat().st_size
            if compressed_size == 0:
                print(f"Warning: Compressed archive empty for {tar_path.name}")
                out_path.unlink()
                return False
            if compressed_size < tar_size:
                tar_path.unlink()
                reduction = (tar_size - compressed_size) / tar_size * 100
                print(f"  ✓ Compressed archive: {reduction:.1f}% saved ({fsz(tar_size)} → {fsz(compressed_size)})")
                return True
            else:
                print(f"  ✗ Archive compression didn't save space, keeping .tar")
                out_path.unlink()
                return False
        return False
    except Exception as e:
        print(f"  ✗ Failed to compress tar archive: {e}")
        return False


async def compress_folder_async(folder_path: Path, output_base_name: str, compressor: str) -> bool:
    loop = asyncio.get_running_loop()
    if compressor == "py7zr":
        out_path = Path(output_base_name + ".7z")
        try:

            def compress_7z() -> None:
                with py7zr.SevenZipFile(
                    out_path,
                    mode="w",
                    filters=COMPRESSORS["py7zr"]["settings"]["filters"],
                    dictionary_size=COMPRESSORS["py7zr"]["settings"]["dictionary_size"],
                    solid=COMPRESSORS["py7zr"]["settings"]["solid"],
                ) as sevenz:
                    sevenz.writeall(folder_path, arcname=folder_path.name)

            await loop.run_in_executor(None, compress_7z)
            if out_path.exists():
                original_size = sum(f.stat().st_size for f in folder_path.rglob("*") if f.is_file())
                compressed_size = out_path.stat().st_size
                if compressed_size < original_size:
                    await loop.run_in_executor(None, shutil.rmtree, folder_path)
                    reduction = (original_size - compressed_size) / original_size * 100
                    print(
                        f"  ✓ Compressed archive: {reduction:.1f}% saved ({fsz(original_size)} → {fsz(compressed_size)})"
                    )
                    return True
                else:
                    print(f"  ✗ Archive compression didn't save space")
                    out_path.unlink()
                    return False
            return False
        except Exception as e:
            print(f"Failed to compress folder {folder_path.name}: {e}")
            if out_path.exists():
                out_path.unlink()
            return False
    else:
        tar_path = Path(output_base_name + ".tar")
        out_path = Path(output_base_name + COMPRESSORS[compressor]["tar_ext"])
        try:
            print(f"  Creating tar archive...")
            success = await loop.run_in_executor(None, create_tar_archive, folder_path, tar_path)
            if not success or not tar_path.exists():
                print(f"  Failed to create tar archive")
                return False
            print(f"  Compressing tar archive with {compressor.upper()}...")
            if compress_tar_archive(tar_path, out_path, compressor):
                await loop.run_in_executor(None, shutil.rmtree, folder_path)
                return True
            return False
        except Exception as e:
            print(f"Failed to compress folder {folder_path.name}: {e}")
            if tar_path.exists():
                tar_path.unlink()
            if out_path.exists():
                out_path.unlink()
            return False


def decompress_file(path: Path, compressor: str) -> bool:
    try:
        compressed_data = path.read_bytes()
        if not compressed_data:
            return False
        if compressor == "py7zr":
            decompressed_data = decompress_with_py7zr(compressed_data)
        else:
            decompressed_data = COMPRESSORS[compressor]["decompress"](compressed_data)
        out_path = path.with_suffix("")
        out_path.write_bytes(decompressed_data)
        original_size = path.stat().st_size
        decompressed_size = out_path.stat().st_size
        print(f"  ✓ Decompressed {path.name}: {fsz(original_size)} → {fsz(decompressed_size)}")
        path.unlink()
        return True
    except Exception as e:
        print(f"  ✗ Failed to decompress {path.name}: {e}")
        return False


def extract_tar_archive(tar_path: Path, extract_dir: Path) -> bool:
    try:
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(path=extract_dir)
        return True
    except Exception as e:
        print(f"  Failed to extract tar archive: {e}")
        return False


def decompress_archive(archive_path: Path, compressor: str) -> bool:
    try:
        if compressor == "py7zr":
            extract_dir = archive_path.with_suffix("")
            with py7zr.SevenZipFile(archive_path, mode="r") as sevenz:
                sevenz.extractall(path=extract_dir)
            original_size = archive_path.stat().st_size
            decompressed_size = sum(f.stat().st_size for f in extract_dir.rglob("*") if f.is_file())
            print(f"  ✓ Extracted {archive_path.name}: {fsz(original_size)} → {fsz(decompressed_size)}")
            archive_path.unlink()
            return True
        else:
            tar_path = archive_path.with_suffix("")
            compressed_data = archive_path.read_bytes()
            tar_data = COMPRESSORS[compressor]["decompress"](compressed_data)
            tar_path.write_bytes(tar_data)
            extract_dir = archive_path.stem
            extract_tar_archive(tar_path, Path(extract_dir))
            tar_path.unlink()
            archive_path.unlink()
            print(f"  ✓ Extracted {archive_path.name} to {extract_dir}/")
            return True
    except Exception as e:
        print(f"  ✗ Failed to decompress archive {archive_path.name}: {e}")
        return False


def get_files(directory: Path, compressor: str, mode: str = "compress") -> list[Path]:
    if mode == "compress":
        return [p for p in directory.glob("*") if p.is_file() and not p.is_symlink() and should_compress(p, compressor)]
    else:
        ext = COMPRESSORS[compressor]["ext"]
        return [p for p in directory.glob(f"*{ext}") if p.is_file() and not p.is_symlink()]


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
