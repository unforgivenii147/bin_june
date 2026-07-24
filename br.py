#!/data/data/com.termux/files/home/.local/bin/python

import argparse
import io
import os
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import brotli

CHUNK_SIZE = 1024 * 64
SKIP_PATTERNS = {".", "..", ".git", "__pycache__", ".DS_Store", "thumbs.db"}


def get_brotli_quality(file_size: int) -> int:
    """Determine optimal Brotli quality based on file size."""
    return 11 if file_size < 1024 * 1024 else 9


def compress_stream(input_stream, output_file_path: Path, file_size: int) -> bool:
    """Compress a stream using Brotli and write to file."""
    quality = get_brotli_quality(file_size)
    compressor = brotli.Compressor(quality=quality)
    try:
        with open(output_file_path, "wb") as f_out:
            while True:
                chunk = input_stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                f_out.write(compressor.process(chunk))
            f_out.write(compressor.finish())
        print(f"✅ Compressed (Q={quality}): {output_file_path.name}")
        return True
    except Exception as e:
        print(f"❌ Error compressing {output_file_path.name}: {e}")
        # Clean up failed compression file
        if output_file_path.exists():
            output_file_path.unlink()
        return False


def should_skip_path(path: Path) -> bool:
    """Check if path should be skipped based on patterns."""
    # Skip hidden files/dirs and known patterns
    if any(part.startswith(".") and part not in {".", ".."} for part in path.parts):
        return True
    # Skip known ignore patterns
    if path.name in SKIP_PATTERNS:
        return True
    return False


def process_directory_compress(dir_path: Path) -> bool:
    """Compress a directory to tar.br file."""
    output_br = dir_path.with_name(f"{dir_path.name}.tar.br")

    # Skip if already compressed
    if output_br.exists():
        print(f"⏭️ Skipping (already exists): {output_br.name}")
        return False

    tar_buffer = io.BytesIO()
    try:
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            tar.add(dir_path, arcname=dir_path.name)
        tar_size = tar_buffer.tell()
        tar_buffer.seek(0)

        success = compress_stream(tar_buffer, output_br, tar_size)

        # Remove original directory if compression successful
        if success:
            try:
                import shutil

                shutil.rmtree(dir_path)
                print(f"🗑️ Removed original directory: {dir_path.name}")
            except Exception as e:
                print(f"⚠️ Could not remove directory {dir_path.name}: {e}")

        return success
    except Exception as e:
        print(f"❌ Failed to archive directory {dir_path.name}: {e}")
        return False
    finally:
        tar_buffer.close()


def process_file_compress(file_path: Path) -> bool:
    """Compress a single file to .br file."""
    output_br = file_path.with_name(f"{file_path.name}.br")

    # Skip if already compressed or if it's a .br file itself
    if output_br.exists():
        print(f"⏭️ Skipping (already exists): {output_br.name}")
        return False

    # Skip self (this script)
    if file_path.name == Path(__file__).name:
        return False

    try:
        file_size = file_path.stat().st_size
        with open(file_path, "rb") as f_in:
            success = compress_stream(f_in, output_br, file_size)

        # Remove original file if compression successful
        if success:
            try:
                file_path.unlink()
                print(f"🗑️ Removed original file: {file_path.name}")
            except Exception as e:
                print(f"⚠️ Could not remove file {file_path.name}: {e}")

        return success
    except Exception as e:
        print(f"❌ Failed to read file {file_path.name}: {e}")
        return False


def decompress_stream(input_file_path: Path) -> io.BytesIO:
    """Decompress a Brotli compressed file."""
    decompressor = brotli.Decompressor()
    out_buffer = io.BytesIO()
    try:
        with open(input_file_path, "rb") as f_in:
            while True:
                chunk = f_in.read(CHUNK_SIZE)
                if not chunk:
                    break
                out_buffer.write(decompressor.decompress(chunk))
        out_buffer.seek(0)
        return out_buffer
    except brotli.error as e:
        raise Exception(f"Brotli decompression error: {e}")


def handle_decompress(file_path: Path) -> bool:
    """Decompress a .br or .tar.br file."""
    try:
        decompressed_mem = decompress_stream(file_path)

        if file_path.name.endswith(".tar.br"):
            with tarfile.open(fileobj=decompressed_mem, mode="r:") as tar:
                tar.extractall(path=file_path.parent)
            print(f"🔓 Extracted and unpacked archive: {file_path.name}")
        else:
            output_name = file_path.with_name(file_path.stem)
            with open(output_name, "wb") as f_out:
                f_out.write(decompressed_mem.read())
            print(f"🔓 Decompressed file: {file_path.name} -> {output_name.name}")

        # Remove compressed file after successful decompression
        try:
            file_path.unlink()
            print(f"🗑️ Removed compressed file: {file_path.name}")
        except Exception as e:
            print(f"⚠️ Could not remove compressed file {file_path.name}: {e}")

        return True
    except Exception as e:
        print(f"❌ Failed to decompress {file_path.name}: {e}")
        return False
    finally:
        if "decompressed_mem" in locals():
            decompressed_mem.close()


def get_directory_size(dir_path: Path) -> int:
    """Calculate total size of all files in directory recursively."""
    try:
        return sum(f.stat().st_size for f in dir_path.rglob("*") if f.is_file() and not should_skip_path(f))
    except Exception:
        return 0


def gather_compression_targets() -> list:
    """Gather all valid compression targets."""
    current_dir = Path(".")
    work_items = []

    # Gather directories
    for d in current_dir.iterdir():
        if not d.is_dir():
            continue
        if should_skip_path(d):
            continue
        # Skip if .tar.br already exists
        if d.with_name(f"{d.name}.tar.br").exists():
            continue
        work_items.append((get_directory_size(d), process_directory_compress, d))

    # Gather files
    for f in current_dir.iterdir():
        if not f.is_file():
            continue
        if should_skip_path(f):
            continue
        if f.name == Path(__file__).name:
            continue
        if f.suffix == ".br":
            continue
        # Skip if .br already exists
        if f.with_name(f"{f.name}.br").exists():
            continue
        try:
            work_items.append((f.stat().st_size, process_file_compress, f))
        except OSError:
            continue

    return work_items


def run_compression():
    """Execute compression on all valid targets."""
    work_items = gather_compression_targets()

    if not work_items:
        print("No matchable subdirectories or files found to compress.")
        return

    work_items.sort(key=lambda x: x[0], reverse=True)
    print(f"🚀 Found {len(work_items)} items. Launching parallel compression (Largest first)...")

    success_count = 0
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(func, target): target for _, func, target in work_items}

        for future in as_completed(futures):
            target = futures[future]
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                print(f"❌ Unexpected error with {target}: {e}")

    print(f"📊 Compression complete: {success_count}/{len(work_items)} successful")


def gather_decompression_targets() -> list:
    """Gather all valid decompression targets."""
    current_dir = Path(".")
    br_files = []

    for f in current_dir.rglob("*"):
        if not f.is_file():
            continue
        if not f.name.endswith(".br"):
            continue
        if should_skip_path(f):
            continue

        # Check if decompressed file already exists
        if f.name.endswith(".tar.br"):
            extracted_dir = f.parent / f.name[:-7]  # Remove .tar.br
            if extracted_dir.exists():
                print(f"⏭️ Skipping (directory exists): {extracted_dir.name}")
                continue
        else:
            decompressed_file = f.with_name(f.stem)  # Remove .br
            if decompressed_file.exists():
                print(f"⏭️ Skipping (file exists): {decompressed_file.name}")
                continue

        br_files.append(f)

    return br_files


def run_decompression():
    """Execute decompression on all valid targets."""
    br_files = gather_decompression_targets()

    if not br_files:
        print("No compressed .br or .tar.br targets located inside execution directory structure.")
        return

    print(f"🚀 Found {len(br_files)} compressed targets. Spawning parallel decompression pool...")

    success_count = 0
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(handle_decompress, file): file for file in br_files}

        for future in as_completed(futures):
            file = futures[future]
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                print(f"❌ Unexpected error with {file.name}: {e}")

    print(f"📊 Decompression complete: {success_count}/{len(br_files)} successful")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="Parallel Brotli File/Folder Compression Tool with cleanup")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c", "--compress", action="store_true", help="Compress recursive targets (default action)")
    group.add_argument("-d", "--decompress", action="store_true", help="Decompress recursive targets")
    args = parser.parse_args()

    # Default to compress if no action specified
    if not args.decompress:
        args.compress = True

    if args.compress:
        run_compression()
    elif args.decompress:
        run_decompression()

    print("🎉 Action lifecycle execution pool finalized.")


if __name__ == "__main__":
    main()
