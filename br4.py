#!/data/data/com.termux/files/usr/bin/python


"""
Brotli Compression/Decompression Tool

A script that compresses or decompresses files/directories using brotlicffi.
Supports multi-threading for compression and decompression operations.

Usage:
    python brotli_tool.py                    # Compress current directory recursively
    python brotli_tool.py -c <path>          # Compress file or directory
    python brotli_tool.py -d <path>          # Decompress file or directory
"""

import argparse
import os
import shutil
import sys
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import brotlicffi


def compress_file(input_path: (Path | str), output_path: (Path | str), quality=6):
    try:
        with open(input_path, "rb") as f:
            data = f.read()
        compressor = brotlicffi.Compressor(quality=quality)
        compressed = compressor.process(data)
        compressed += compressor.finish()
        with open(output_path, "wb") as f:
            f.write(compressed)
        original_size = len(data)
        compressed_size = len(compressed)
        ratio = compressed_size / original_size * 100 if original_size > 0 else 0
        return {
            "success": True,
            "input": input_path,
            "output": output_path,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "ratio": ratio,
        }
    except Exception as e:
        return {"success": False, "input": input_path, "error": str(e)}


def decompress_file(input_path: (Path | str), output_path: (Path | str)):
    try:
        with open(input_path, "rb") as f:
            compressed_data = f.read()
        decompressor = brotlicffi.Decompressor()
        decompressed = decompressor.process(compressed_data)
        if not decompressor.is_finished():
            decompressed += decompressor.finish()
        with open(output_path, "wb") as f:
            f.write(decompressed)
        return {
            "success": True,
            "input": input_path,
            "output": output_path,
            "original_size": len(compressed_data),
            "decompressed_size": len(decompressed),
        }
    except Exception as e:
        return {"success": False, "input": input_path, "error": str(e)}


def compress_directory_to_tar(input_dir: str, quality=6) -> Path | None:
    input_path = Path(input_dir)
    tar_path = input_path.with_suffix(".tar")
    compressed_path = input_path.with_suffix(".tar.br")
    try:
        print(f"  Creating tar archive: {tar_path.name}")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(input_path, arcname=input_path.name)
        print(f"  Compressing tar archive: {compressed_path.name}")
        result = compress_file(tar_path, compressed_path, quality)
        if result["success"]:
            shutil.rmtree(input_path)
            os.remove(tar_path)
            return compressed_path
        else:
            if tar_path.exists():
                os.remove(tar_path)
            return None
    except Exception as e:
        print(f"  Error compressing directory: {e}")
        if tar_path.exists():
            os.remove(tar_path)
        return None


def decompress_tar_br(input_path: str, output_dir=None) -> Path | None:
    input_path = Path(input_path)
    if not input_path.suffixes == [".tar", ".br"]:
        print(f"  Error: {input_path} is not a .tar.br file")
        return None
    if output_dir is None:
        output_path = input_path.parent / input_path.stem.replace(".tar", "")
    else:
        output_path = Path(output_dir) / input_path.stem.replace(".tar", "")
    tar_path = input_path.with_suffix("")
    try:
        print(f"  Decompressing: {input_path.name}")
        result = decompress_file(input_path, tar_path)
        if not result["success"]:
            return None
        print(f"  Extracting: {tar_path.name}")
        with tarfile.open(tar_path, "r") as tar:
            extract_dir = output_path.parent
            tar.extractall(path=extract_dir)
        os.remove(tar_path)
        os.remove(input_path)
        return output_path
    except Exception as e:
        print(f"  Error decompressing {input_path}: {e}")
        if tar_path.exists():
            os.remove(tar_path)
        return None


def compress_path(input_path: str, quality: int = 6, max_workers: int = 4) -> bool | None:
    path = Path(input_path)
    if not path.exists():
        print(f"Error: Path '{input_path}' does not exist")
        return False
    if path.is_file():
        compressed_path = path.with_suffix(f"{path.suffix}.br")
        if path.suffix == ".tar":
            compressed_path = path.with_suffix(".tar.br")
        print(f"Compressing file: {path}")
        result = compress_file(str(path), str(compressed_path), quality)
        if result["success"]:
            os.remove(path)
            print(f"✓ Compression successful!")
            print(f"  Original: {result['original_size']:,} bytes")
            print(f"  Compressed: {result['compressed_size']:,} bytes")
            print(f"  Ratio: {result['ratio']:.1f}%")
            print(f"  Output: {result['output']}")
            return True
        else:
            print(f"✗ Compression failed: {result['error']}")
            return False
    elif path.is_dir():
        if path.suffix == ".br":
            print(f"Error: Cannot compress a .br directory")
            return False
        print(f"Compressing directory: {path}")
        compressed_path = compress_directory_to_tar(str(path), quality)
        if compressed_path:
            print(f"✓ Directory compression successful!")
            print(f"  Output: {compressed_path}")
            return True
        else:
            print(f"✗ Directory compression failed")
            return False


def decompress_path(input_path: str, max_workers: int = 4) -> bool | None:
    path = Path(input_path)
    if not path.exists():
        print(f"Error: Path '{input_path}' does not exist")
        return False
    if path.is_file():
        if path.suffixes == [".tar", ".br"]:
            print(f"Decompressing tar archive: {path}")
            output_dir = decompress_tar_br(str(path))
            if output_dir:
                print(f"✓ Decompression successful!")
                print(f"  Extracted to: {output_dir}")
                return True
            else:
                print(f"✗ Decompression failed")
                return False
        elif path.suffix == ".br":
            output_path = path.with_suffix("")
            print(f"Decompressing file: {path}")
            result = decompress_file(str(path), str(output_path))
            if result["success"]:
                os.remove(path)
                print(f"✓ Decompression successful!")
                print(f"  Original: {result['original_size']:,} bytes")
                print(f"  Decompressed: {result['decompressed_size']:,} bytes")
                print(f"  Output: {result['output']}")
                return True
            else:
                print(f"✗ Decompression failed: {result['error']}")
                return False
        else:
            print(f"Error: '{path}' doesn't have .br extension")
            return False
    elif path.is_dir():
        br_files = list(path.rglob("*.br"))
        tar_br_files = [f for f in br_files if f.suffixes == [".tar", ".br"]]
        regular_br_files = [f for f in br_files if f.suffix == ".br" and f not in tar_br_files]
        if not br_files:
            print(f"No compressed files found in '{path}'")
            return False
        print(f"Found {len(br_files)} compressed files to decompress")
        success_count = 0
        for tar_br_file in tar_br_files:
            print(f"\nProcessing: {tar_br_file.relative_to(path)}")
            if decompress_tar_br(str(tar_br_file)):
                success_count += 1
        if regular_br_files:
            print(
                f"""
Decompressing {len(regular_br_files)} regular files using {max_workers} threads..."""
            )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for br_file in regular_br_files:
                    output_path = br_file.with_suffix("")
                    future = executor.submit(decompress_file, str(br_file), str(output_path))
                    futures.append((future, br_file))
                for future, br_file in futures:
                    result = future.result()
                    if result["success"]:
                        os.remove(result["input"])
                        print(f"  ✓ Decompressed: {result['output']}")
                        success_count += 1
                    else:
                        print(f"  ✗ Failed: {br_file} - {result['error']}")
        print(f"\n{'=' * 60}")
        print(f"Decompression Complete!")
        print(f"  Files decompressed: {success_count}/{len(br_files)}")
        print(f"{'=' * 60}")
        return success_count > 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compress or decompress files/directories using Brotli",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compress current directory (default when no args)
  python brotli_tool.py
  
  # Compress a single file
  python brotli_tool.py -c document.txt
  
  # Compress a directory (creates .tar.br)
  python brotli_tool.py -c myfolder -q 11
  
  # Decompress a file
  python brotli_tool.py -d document.txt.br
  
  # Decompress a .tar.br file (extracts to directory)
  python brotli_tool.py -d myfolder.tar.br
  
  # Decompress all files in a directory
  python brotli_tool.py -d compressed_folder -t 8
        """,
    )
    parser.add_argument(
        "-c",
        "--compress",
        metavar="PATH",
        nargs="?",
        const=".",
        help="Compress the specified file or directory (default: current directory if no path given)",
    )
    parser.add_argument(
        "-d",
        "--decompress",
        metavar="PATH",
        nargs="?",
        const=".",
        help="Decompress the specified file or directory (default: current directory if no path given)",
    )
    parser.add_argument(
        "-q",
        "--quality",
        type=int,
        default=6,
        choices=range(0, 12),
        help="Compression quality (0-11, default: 6). Higher = better compression but slower",
    )
    parser.add_argument(
        "-t", "--threads", type=int, default=4, help="Number of threads for parallel processing (default: 4)"
    )
    args = parser.parse_args()
    if not args.compress and not args.decompress:
        print("No arguments provided. Compressing current directory...")
        args.compress = "."
    if args.compress:
        if args.compress == ".":
            path = Path.cwd()
        else:
            path = Path(args.compress)
        success = compress_path(str(path), args.quality, args.threads)
        sys.exit(0 if success else 1)
    elif args.decompress:
        if args.decompress == ".":
            path = Path.cwd()
        else:
            path = Path(args.decompress)
        success = decompress_path(str(path), args.threads)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
