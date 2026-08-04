#!/data/data/com.termux/files/home/.local/bin/python
import argparse
import io
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import zstandard as zstd

ZSTD_LEVEL = 19
CHUNK_SIZE = 1024 * 64


def compress_stream(input_stream, output_file_path: Path) -> bool:
    """Compress using Zstandard (level 19)"""
    try:
        cctx = zstd.ZstdCompressor(level=ZSTD_LEVEL)
        with open(output_file_path, "wb") as f_out:
            compressor = cctx.stream_writer(f_out)
            while True:
                chunk = input_stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                compressor.write(chunk)
            compressor.close()  # Important for Zstd
        print(f"✅ Compressed: {output_file_path.name}")
        return True
    except Exception as e:
        print(f"❌ Error compressing to {output_file_path.name}: {e}")
        return False


def decompress_stream(input_path: Path, output_path: Path) -> bool:
    """Decompress Zstandard file"""
    try:
        dctx = zstd.ZstdDecompressor()
        with open(input_path, "rb") as f_in:
            with open(output_path, "wb") as f_out:
                decompressor = dctx.stream_reader(f_in)
                while True:
                    chunk = decompressor.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f_out.write(chunk)
        print(f"✅ Decompressed: {output_path.name}")
        return True
    except Exception as e:
        print(f"❌ Error decompressing {input_path.name}: {e}")
        return False


def process_directory(dir_path: Path):
    """Compress directory → .tar.zst"""
    output_zst = dir_path.with_name(f"{dir_path.name}.tar.zst")
    tar_buffer = io.BytesIO()

    try:
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            tar.add(dir_path, arcname=dir_path.name)

        tar_buffer.seek(0)
        if compress_stream(tar_buffer, output_zst):
            import shutil

            shutil.rmtree(dir_path)
            print(f"🗑️  Removed original directory: {dir_path.name}")
    except Exception as e:
        print(f"❌ Failed to archive directory {dir_path.name}: {e}")


def process_file(file_path: Path):
    """Compress single file → .zst"""
    output_zst = file_path.with_name(f"{file_path.name}.zst")
    try:
        with open(file_path, "rb") as f_in:
            if compress_stream(f_in, output_zst):
                file_path.unlink()
                print(f"🗑️  Removed original file: {file_path.name}")
    except Exception as e:
        print(f"❌ Failed to compress file {file_path.name}: {e}")


def decompress_file(zst_path: Path):
    """Decompress .zst or .tar.zst file"""
    if zst_path.name.endswith(".tar.zst"):
        # .tar.zst → directory
        output_dir = zst_path.with_name(zst_path.name[:-8])  # remove .tar.zst
        tar_buffer = io.BytesIO()

        try:
            if decompress_stream(zst_path, tar_buffer):
                tar_buffer.seek(0)
                with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                    tar.extractall(path=output_dir.parent)
                zst_path.unlink()
                print(f"🗑️  Removed archive: {zst_path.name}")
        except Exception as e:
            print(f"❌ Failed to decompress tar archive {zst_path.name}: {e}")

    elif zst_path.suffix == ".zst":
        # Regular .zst → original file
        output_file = zst_path.with_suffix("")
        if decompress_stream(zst_path, output_file):
            zst_path.unlink()
            print(f"🗑️  Removed archive: {zst_path.name}")
    else:
        print(f"⚠️  Skipping non-zst file: {zst_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Compress/Decompress with Zstandard (zstd)")
    parser.add_argument("-c", "--compress", action="store_true", help="Compress mode (default)")
    parser.add_argument("-d", "--decompress", action="store_true", help="Decompress mode")

    args = parser.parse_args()

    mode = "decompress" if args.decompress else "compress"

    current_dir = Path(".")

    if mode == "compress":
        subdirs = [d for d in current_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        files = [
            f for f in current_dir.iterdir() if f.is_file() and f.suffix != ".zst" and f.name != Path(__file__).name
        ]

        if not subdirs and not files:
            print("No files or subdirectories found to compress.")
            return

        print(f"🚀 Found {len(subdirs)} subdirs and {len(files)} files to compress.")
        print(f"⚡ Starting parallel Zstandard compression (Level: {ZSTD_LEVEL})...")

        with ThreadPoolExecutor() as executor:
            for d in subdirs:
                executor.submit(process_directory, d)
            for f in files:
                executor.submit(process_file, f)

    else:  # decompress
        archives = [f for f in current_dir.iterdir() if f.is_file() and f.suffix == ".zst"]

        if not archives:
            print("No .zst or .tar.zst files found to decompress.")
            return

        print(f"🚀 Found {len(archives)} archives to decompress.")
        print("⚡ Starting parallel decompression...")

        with ThreadPoolExecutor() as executor:
            for archive in archives:
                executor.submit(decompress_file, archive)

    print("🎉 All operations completed successfully!")


if __name__ == "__main__":
    main()
