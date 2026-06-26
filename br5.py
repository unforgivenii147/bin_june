#!/data/data/com.termux/files/usr/bin/python
import os
import sys
import brotli
import tarfile
from pathlib import Path


def compress_file_in_chunks(input_path, output_path, chunk_size=65536, quality=5):
    """
    Compress a single file using Brotli, reading and compressing in chunks.

    Args:
        input_path (str): Path to the input file.
        output_path (str): Path for the output .br file.
        chunk_size (int): Size of each chunk to read (default 64KB).
        quality (int): Brotli compression quality (0-11, default 5).
    """
    compressor = brotli.Compressor(quality=quality)

    with open(input_path, "rb") as f_in, open(output_path, "wb") as f_out:
        while True:
            chunk = f_in.read(chunk_size)
            if not chunk:
                break
            # Compress the chunk incrementally
            compressed_chunk = compressor.compress(chunk)
            if compressed_chunk:
                f_out.write(compressed_chunk)

        # Finalize the compressor to flush remaining data
        final_data = compressor.finish()
        if final_data:
            f_out.write(final_data)

    print(f"Compressed: {input_path} -> {output_path}")


def compress_folder(input_path, output_path, chunk_size=65536, quality=5):
    """
    Compress an entire folder into a tar archive, then compress the tar with Brotli.

    Args:
        input_path (str): Path to the folder to compress.
        output_path (str): Path for the output .tar.br file.
        chunk_size (int): Size of each chunk to read (default 64KB).
        quality (int): Brotli compression quality (0-11, default 5).
    """
    # Create a temporary tar file in memory
    import io

    tar_buffer = io.BytesIO()

    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        tar.add(input_path, arcname=os.path.basename(input_path))

    # Get the tar data
    tar_buffer.seek(0)

    # Compress the tar data in chunks using Brotli
    compressor = brotli.Compressor(quality=quality)

    with open(output_path, "wb") as f_out:
        while True:
            chunk = tar_buffer.read(chunk_size)
            if not chunk:
                break
            compressed_chunk = compressor.compress(chunk)
            if compressed_chunk:
                f_out.write(compressed_chunk)

        final_data = compressor.finish()
        if final_data:
            f_out.write(final_data)

    print(f"Compressed folder: {input_path} -> {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python compress_brotli.py <path_to_file_or_folder> [output_path]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(input_path):
        print(f"Error: Path '{input_path}' does not exist.")
        sys.exit(1)

    # Determine output path if not provided
    if output_path is None:
        if os.path.isfile(input_path):
            output_path = input_path + ".br"
        else:
            output_path = input_path.rstrip("/") + ".tar.br"

    # Compress based on whether input is a file or folder
    if os.path.isfile(input_path):
        compress_file_in_chunks(input_path, output_path)
    elif os.path.isdir(input_path):
        compress_folder(input_path, output_path)
    else:
        print(f"Error: '{input_path}' is neither a file nor a folder.")
        sys.exit(1)


if __name__ == "__main__":
    main()
