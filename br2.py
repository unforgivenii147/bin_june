#!/data/data/com.termux/files/home/.local/bin/python
import os
import tarfile
import io
import brotli
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Adjust quality: 1-3 is fast, 4-9 is balanced, 11 is tightest but slowest
BROTLI_QUALITY = 4
CHUNK_SIZE = 1024 * 64  # 64KB chunks for streaming memory efficiency


def compress_stream(input_stream, output_file_path: Path):
    """Streams data from a file-like object into a .br file using Brotli's streaming API."""
    compressor = brotli.Compressor(quality=BROTLI_QUALITY)

    try:
        with open(output_file_path, "wb") as f_out:
            while True:
                chunk = input_stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                # Compress chunk and write any available bytes out immediately
                f_out.write(compressor.process(chunk))
            # Flush final internal compression buffers to disk
            f_out.write(compressor.finish())
        print(f"✅ Compressed: {output_file_path.name}")
    except Exception as e:
        print(f"❌ Error compressing {output_file_path.name}: {e}")


def process_directory(dir_path: Path):
    """Tars a subdirectory entirely in memory and streams it into a .tar.br file."""
    output_br = dir_path.with_name(f"{dir_path.name}.tar.br")

    # Create an in-memory byte buffer to hold the tar archive
    tar_buffer = io.BytesIO()

    try:
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            # arcname prevents preserving full absolute paths inside the archive
            tar.add(dir_path, arcname=dir_path.name)

        # Reset memory pointer to the beginning before streaming out
        tar_buffer.seek(0)
        compress_stream(tar_buffer, output_br)
    except Exception as e:
        print(f"❌ Failed to archive directory {dir_path.name}: {e}")


def process_file(file_path: Path):
    """Streams a regular file into a .br file."""
    output_br = file_path.with_name(f"{file_path.name}.br")
    try:
        with open(file_path, "rb") as f_in:
            compress_stream(f_in, output_br)
    except Exception as e:
        print(f"❌ Failed to open file {file_path.name}: {e}")


def main():
    current_dir = Path(".")

    # 1. Isolate items in the current directory root (avoiding infinite recursive loops)
    subdirs = [d for d in current_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    files = [f for f in current_dir.iterdir() if f.is_file() and f.suffix != ".br" and f.name != Path(__file__).name]

    if not subdirs and not files:
        print("No files or subdirectories found to compress.")
        return

    print(f"🚀 Found {len(subdirs)} subdirs to TAR+BR, and {len(files)} files to BR.")
    print(f"⚡ Starting parallel processing pool (Quality Level: {BROTLI_QUALITY})...")

    # ThreadPoolExecutor maximizes throughput on multi-core systems
    with ThreadPoolExecutor() as executor:
        # Submit all directory tar jobs
        for directory in subdirs:
            executor.submit(process_directory, directory)

        # Submit all isolated file jobs
        for file in files:
            executor.submit(process_file, file)

    print("🎉 All operations completed successfully!")


if __name__ == "__main__":
    main()
