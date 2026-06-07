#!/data/data/com.termux/files/usr/bin/python

import asyncio
import mmap
import shutil
import sys
from pathlib import Path

from dh import mpf3
from lzma_mt import compress

_executor = asyncio.Semaphore(4)
CHUNK_SIZE = 524288


def compress_in_memory(infile, outfile):
    try:
        outfile.write_bytes(compress(infile.read_bytes(), preset=7, threads=4))
        return True
    except:
        return False


def compress_chunk(data):
    return compress(data, preset=7, threads=4)


def compress_chunked(in_path, out_path, file_size):
    try:
        chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        with out_path.open("wb", buffering=1024 * 1024) as fout, in_path.open("rb") as fin:
            mm = mmap.mmap(fin.fileno(), length=0, access=mmap.ACCESS_READ)
            chunks = [mm[i * CHUNK_SIZE : min((i + 1) * CHUNK_SIZE, file_size)] for i in range(chunk_count)]
            compressed_chunks = mpf3(compress_chunk, chunks)
            for block in compressed_chunks:
                fout.write(block)
            mm.close()
            return True
    except OSError:
        return False


def fsz(size: float) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if abs(size) < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PiB"


async def compress_folder_async(folder_path: Path, output_base_name: str, format="tar") -> bool:
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, lambda: shutil.make_archive(output_base_name, format, str(folder_path)))
        return True
    except Exception as e:
        print(f"Failed to compress folder {folder_path} → {output_base_name}: {e}")
        return False


def compress_file(path: Path) -> bool:
    out_path = path.with_suffix(path.suffix + ".xz")
    if out_path.exists():
        return False
    original_size = path.stat().st_size
    if not original_size:
        return False
    if original_size < CHUNK_SIZE:
        success = compress_in_memory(path, out_path)
    else:
        success = compress_chunked(path, out_path, original_size)
    if success:
        compressed_size = out_path.stat().st_size
        if not compressed_size:
            print(f"Compressed file empty: {out_path}")
            return False
        path.unlink()
        reduction = (original_size - compressed_size) / original_size * 100
        print(f"{path.name} | {reduction:.2f}%")
        return True
    else:
        print(f"Compression failed for {path}")
        return False


def get_files(directory: Path) -> list[Path]:
    return [p for p in directory.glob("*") if p.is_file() and (not p.is_symlink()) and should_compress(p)]


def get_dirs(directory: Path) -> list[Path]:
    return [p for p in directory.glob("*") if not p.is_symlink() and p.is_dir()]


def should_compress(path):
    path = Path(path)
    try:
        if path.is_symlink():
            return False
        if not path.is_file():
            return False
        compressed_extensions = (".xz", ".br", ".7z")
        if path.suffix in compressed_extensions:
            return False
        return path.stat().st_size
    except (OSError, PermissionError):
        return False


async def main_async() -> None:
    sys.argv[1:]
    cwd = Path.cwd()
    dirs_to_compress = get_dirs(cwd)
    if dirs_to_compress:
        for dir_path in sorted(dirs_to_compress):
            print(f"compressing {dir_path.relative_to(cwd)}")
            if await compress_folder_async(dir_path, str(dir_path.parent / dir_path.name), format="tar"):
                print(f"compressed {dir_path.relative_to(cwd)}")
                shutil.rmtree(dir_path)
    files_to_compress = get_files(cwd)
    if not files_to_compress:
        print("No files to compress")
        return
    total_original = 0
    total_compressed = 0
    successful = 0
    for i, path in enumerate(sorted(files_to_compress), 1):
        print(f"\n[{i}/{len(files_to_compress)}] {path.name}")
        orig_size = path.stat().st_size
        total_original += orig_size
        if compress_file(path):
            successful += 1
        out_path = path.with_suffix(path.suffix + ".xz")
        if out_path.exists():
            total_compressed += out_path.stat().st_size
    if successful > 0:
        savings = total_original - total_compressed
        savings_percent = savings / total_original * 100
        print(f"Space saved: {fsz(savings)} {savings_percent:.1f}%")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
