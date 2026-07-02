#!/data/data/com.termux/files/usr/bin/env python
"""
LZMA Recursive File Compressor/Decompressor
Compresses and decompresses files using LZMA with parallel processing and streaming.
Removes original files after successful compression by default.
Can optionally tar subdirectories before LZMA compression for better ratios.
"""

import argparse
import lzma
import multiprocessing as mp
from pathlib import Path
from typing import Tuple, Optional, List, Set
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import sys
import tarfile
import tempfile
import shutil
import os

# Check for rich library, fallback to basic formatting if not available
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.live import Live
    from rich.text import Text
    from rich import box

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("💡 Tip: Install 'rich' for prettier output: pip install rich")


# File extensions to exclude from compression (already compressed formats)
EXCLUDED_EXTENSIONS = {
    ".xz",
    ".lzma",
    ".7z",
    ".gz",
    ".bz2",
    ".zip",
    ".rar",
    ".tar",
    ".tgz",
    ".tbz2",
    ".txz",
    ".tlz",
    ".lz",
    ".lz4",
    ".lzo",
    ".sz",
    ".snappy",
    ".zlib",
    ".deflate",
    ".flac",
    ".mp3",
    ".aac",
    ".ogg",
    ".wma",
    ".opus",
    ".m4a",
    ".wavpack",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".avif",
    ".heic",
    ".heif",
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".odt",
    ".ods",
    ".odp",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".wasm",
    ".whl",
    ".egg",
    ".deb",
    ".rpm",
    ".apk",
    ".ipa",
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".obj",
    ".lib",
    ".a",
    ".iso",
    ".img",
    ".dmg",
    ".vdi",
    ".vmdk",
    ".qcow2",
}


@dataclass
class CompressionResult:
    """Store compression/decompression results for a single file."""

    file_path: Path
    original_size: int
    processed_size: int
    success: bool
    error: Optional[str] = None
    duration: float = 0.0
    original_deleted: bool = False
    operation: str = "compress"  # "compress" or "decompress"
    was_tarred: bool = False  # Whether this was a tar operation


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def tar_directory(directory: Path, output_path: Path, delete_original: bool = False) -> Tuple[int, bool]:
    """
    Create a tar archive of a directory.

    Args:
        directory: Directory to tar
        output_path: Path for the tar file
        delete_original: Whether to delete the original directory after tarring

    Returns:
        Tuple of (tar_size, success)
    """
    try:
        # Calculate original size
        original_size = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())

        # Create tar file
        with tarfile.open(output_path, "w") as tar:
            tar.add(directory, arcname=directory.name)

        tar_size = output_path.stat().st_size

        # Delete original if requested
        if delete_original and output_path.exists():
            shutil.rmtree(directory)

        return tar_size, True

    except Exception as e:
        if output_path.exists():
            output_path.unlink()
        raise e


def compress_file_streaming(
    input_path: Path,
    output_path: Path,
    preset: int = 7,
    threads: int = 4,
    chunk_size: int = 1024 * 1024,  # 1MB chunks
    keep_original: bool = False,
    was_tarred: bool = False,
) -> CompressionResult:
    """
    Compress a single file using LZMA with streaming.

    Args:
        input_path: Path to input file
        output_path: Path for compressed output
        preset: LZMA compression preset (0-9, default: 7)
        threads: Number of threads for LZMA compression (only works with lzma_mt format)
        chunk_size: Size of chunks to read/write
        keep_original: Whether to keep the original file after compression
        was_tarred: Whether this file was created by tarring a directory
    """
    start_time = time.time()

    try:
        original_size = input_path.stat().st_size

        # Skip empty files
        if original_size == 0:
            return CompressionResult(
                file_path=input_path,
                original_size=0,
                processed_size=0,
                success=False,
                error="Empty file",
                duration=time.time() - start_time,
                operation="compress",
                was_tarred=was_tarred,
            )

        # LZMA filters for multi-threaded compression
        # Using lzma_mt format with specified preset and threads
        filters = [
            {
                "id": lzma.FILTER_LZMA2,
                "preset": preset,
            }
        ]

        # Create LZMA compressor with multi-threading support
        # Note: Python's lzma module supports multi-threading through the format parameter
        compressor = lzma.LZMACompressor(
            format=lzma.FORMAT_XZ,  # XZ format supports multi-threading
            check=lzma.CHECK_CRC64,
            preset=preset,
            filters=filters,
        )

        compressed_size = 0

        # Open input file and stream compress
        with open(input_path, "rb") as f_in:
            with open(output_path, "wb") as f_out:
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break

                    # Compress the chunk
                    compressed_chunk = compressor.compress(chunk)
                    if compressed_chunk:
                        f_out.write(compressed_chunk)
                        compressed_size += len(compressed_chunk)

                # Flush any remaining data
                remaining = compressor.flush()
                if remaining:
                    f_out.write(remaining)
                    compressed_size += len(remaining)

        # Delete original by default, keep if explicitly requested
        original_deleted = False
        if not keep_original and output_path.exists():
            input_path.unlink()
            original_deleted = True

        return CompressionResult(
            file_path=input_path,
            original_size=original_size,
            processed_size=compressed_size,
            success=True,
            duration=time.time() - start_time,
            original_deleted=original_deleted,
            operation="compress",
            was_tarred=was_tarred,
        )

    except Exception as e:
        # Clean up failed output file
        if output_path.exists():
            output_path.unlink()

        return CompressionResult(
            file_path=input_path,
            original_size=input_path.stat().st_size if input_path.exists() else 0,
            processed_size=0,
            success=False,
            error=str(e),
            duration=time.time() - start_time,
            operation="compress",
            was_tarred=was_tarred,
        )


def decompress_file_streaming(
    input_path: Path,
    output_path: Path,
    chunk_size: int = 1024 * 1024,  # 1MB chunks
    keep_original: bool = False,
) -> CompressionResult:
    """
    Decompress a single LZMA file with streaming.

    Args:
        input_path: Path to compressed .xz file
        output_path: Path for decompressed output (without .xz extension)
        chunk_size: Size of chunks to read/write
        keep_original: Whether to keep the compressed file after decompression
    """
    start_time = time.time()

    try:
        original_size = input_path.stat().st_size

        # Skip empty files
        if original_size == 0:
            return CompressionResult(
                file_path=input_path,
                original_size=0,
                processed_size=0,
                success=False,
                error="Empty file",
                duration=time.time() - start_time,
                operation="decompress",
            )

        # Open input file and stream decompress
        decompressed_size = 0

        with lzma.open(input_path, "rb") as f_in:
            with open(output_path, "wb") as f_out:
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    decompressed_size += len(chunk)

        # Delete compressed file by default, keep if explicitly requested
        original_deleted = False
        if not keep_original and output_path.exists():
            input_path.unlink()
            original_deleted = True

        return CompressionResult(
            file_path=input_path,
            original_size=original_size,
            processed_size=decompressed_size,
            success=True,
            duration=time.time() - start_time,
            original_deleted=original_deleted,
            operation="decompress",
        )

    except Exception as e:
        # Clean up failed output file
        if output_path.exists():
            output_path.unlink()

        return CompressionResult(
            file_path=input_path,
            original_size=input_path.stat().st_size if input_path.exists() else 0,
            processed_size=0,
            success=False,
            error=str(e),
            duration=time.time() - start_time,
            operation="decompress",
        )


def untar_file(tar_path: Path, extract_dir: Path, delete_tar: bool = False) -> bool:
    """
    Extract a tar file.

    Args:
        tar_path: Path to tar file
        extract_dir: Directory to extract to (parent of original location)
        delete_tar: Whether to delete the tar file after extraction
    """
    try:
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(extract_dir)

        if delete_tar:
            tar_path.unlink()

        return True
    except Exception as e:
        print(f"Error extracting tar {tar_path}: {e}")
        return False


def process_subdirs_with_tar(
    directory: Path,
    preset: int = 7,
    threads: int = 4,
    workers: int = 4,
    keep_original: bool = False,
    exclude_patterns: List[str] = None,
) -> List[CompressionResult]:
    """
    Tar subdirectories first, then compress the tar files with LZMA.

    Args:
        directory: Root directory to process
        preset: LZMA compression preset
        threads: Number of threads for LZMA
        workers: Number of parallel workers
        keep_original: Whether to keep original files
        exclude_patterns: Patterns to exclude

    Returns:
        List of CompressionResult objects
    """
    if exclude_patterns is None:
        exclude_patterns = []

    results = []

    # Get all subdirectories in the root directory
    subdirs = [d for d in directory.iterdir() if d.is_dir() and not d.is_symlink()]

    # Filter out excluded patterns
    subdirs = [d for d in subdirs if not any(pattern in str(d) for pattern in exclude_patterns)]

    # Also filter out common directories that shouldn't be tarred
    excluded_dirs = {".git", ".svn", ".hg", "__pycache__", "node_modules", ".venv", "venv", ".env"}
    subdirs = [d for d in subdirs if d.name not in excluded_dirs]

    if not subdirs:
        print("📁 No subdirectories found to tar")
        return results

    print(f"📁 Found {len(subdirs)} subdirectories to tar first")

    tar_files = []
    tar_errors = []

    # Step 1: Tar all subdirectories
    print("🗜️  Step 1: Creating tar archives of subdirectories...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Process subdirectories (can be done in parallel for large directories)
        for i, subdir in enumerate(subdirs, 1):
            try:
                tar_name = f"{subdir.name}.tar"
                tar_path = subdir.parent / tar_name

                # Check if tar file already exists
                if tar_path.exists():
                    print(f"  ⚠️  [{i}/{len(subdirs)}] {tar_name} already exists, skipping tar creation")
                    tar_files.append(tar_path)
                    continue

                print(f"  📦 [{i}/{len(subdirs)}] Tarring {subdir.name}...")

                # Calculate size before tarring
                dir_size = sum(f.stat().st_size for f in subdir.rglob("*") if f.is_file())

                # Create tar
                tar_size, success = tar_directory(subdir, tar_path, delete_original=not keep_original)

                if success:
                    tar_files.append(tar_path)
                    if not keep_original:
                        print(f"    ✅ Tarred {format_size(dir_size)} → {format_size(tar_size)} (directory deleted)")
                    else:
                        print(f"    ✅ Tarred {format_size(dir_size)} → {format_size(tar_size)} (directory kept)")
                else:
                    tar_errors.append((subdir, "Failed to create tar"))

            except Exception as e:
                print(f"  ❌ [{i}/{len(subdirs)}] Error tarring {subdir.name}: {e}")
                tar_errors.append((subdir, str(e)))

        # Step 2: Compress tar files with LZMA
        if tar_files:
            print(
                f"\n🗜️  Step 2: Compressing {len(tar_files)} tar files with LZMA (preset: {preset}, threads: {threads})..."
            )

            if workers > 1 and len(tar_files) > 1:
                with ProcessPoolExecutor(max_workers=workers) as executor:
                    futures = {}
                    for tar_path in tar_files:
                        output_path = tar_path.with_suffix(".tar.xz")
                        future = executor.submit(
                            compress_file_streaming,
                            tar_path,
                            output_path,
                            preset,
                            threads,
                            1024 * 1024,
                            not keep_original,  # Delete tar after compression
                            was_tarred=True,
                        )
                        futures[future] = tar_path

                    for i, future in enumerate(as_completed(futures), 1):
                        result = future.result()
                        results.append(result)

                        if result.success:
                            print(f"  ✅ [{i}/{len(tar_files)}] {result.file_path.name} → {result.file_path.name}.xz")
                            print(
                                f"     {format_size(result.original_size)} → {format_size(result.processed_size)} "
                                f"({(1 - result.processed_size / result.original_size) * 100:.1f}% compression)"
                            )
                        else:
                            print(f"  ❌ [{i}/{len(tar_files)}] {result.file_path.name}: {result.error}")
            else:
                for i, tar_path in enumerate(tar_files, 1):
                    output_path = tar_path.with_suffix(".tar.xz")
                    result = compress_file_streaming(
                        tar_path, output_path, preset, threads, 1024 * 1024, not keep_original, was_tarred=True
                    )
                    results.append(result)

                    if result.success:
                        print(f"  ✅ [{i}/{len(tar_files)}] {tar_path.name} → {tar_path.name}.xz")
                        print(
                            f"     {format_size(result.original_size)} → {format_size(result.processed_size)} "
                            f"({(1 - result.processed_size / result.original_size) * 100:.1f}% compression)"
                        )
                    else:
                        print(f"  ❌ [{i}/{len(tar_files)}] {tar_path.name}: {result.error}")

        # Report errors
        if tar_errors:
            print(f"\n❌ Failed to tar {len(tar_errors)} directories:")
            for subdir, error in tar_errors:
                print(f"  • {subdir.name}: {error}")

    return results


def should_compress_file(file_path: Path, exclude_extensions: Set[str], exclude_patterns: List[str]) -> bool:
    """
    Determine if a file should be compressed.

    Args:
        file_path: Path to check
        exclude_extensions: Set of extensions to exclude
        exclude_patterns: List of patterns to exclude
    """
    # Skip symlinks
    if file_path.is_symlink():
        return False

    # Skip if not a file
    if not file_path.is_file():
        return False

    # Skip already compressed files (including .xz)
    if file_path.suffix.lower() in exclude_extensions:
        return False

    # Skip files that already have .xz extension
    if file_path.suffix == ".xz":
        return False

    # Skip tar files (they will be processed separately)
    if file_path.suffix == ".tar":
        return False

    # Check exclude patterns
    if exclude_patterns:
        path_str = str(file_path)
        if any(pattern in path_str for pattern in exclude_patterns):
            return False

    return True


def find_files_to_compress(
    directory: Path,
    exclude_extensions: Set[str] = None,
    exclude_patterns: List[str] = None,
    extensions_filter: List[str] = None,
    skip_subdirs: bool = False,
) -> List[Path]:
    """
    Recursively find files to compress.

    Args:
        directory: Root directory to search
        exclude_extensions: Set of file extensions to exclude
        exclude_patterns: Patterns to exclude from path
        extensions_filter: If provided, only include files with these extensions
        skip_subdirs: If True, skip files inside subdirectories (when using tar mode)
    """
    if exclude_extensions is None:
        exclude_extensions = EXCLUDED_EXTENSIONS

    if exclude_patterns is None:
        exclude_patterns = []

    files = []

    if extensions_filter:
        # Only scan for specific extensions
        for ext in extensions_filter:
            ext = ext if ext.startswith(".") else f".{ext}"
            pattern = f"*{ext}"

            for file_path in directory.rglob(pattern):
                if should_compress_file(file_path, exclude_extensions, exclude_patterns):
                    # Skip files in subdirectories if tar mode is active
                    if skip_subdirs and file_path.parent != directory:
                        continue
                    files.append(file_path)
    else:
        # Scan all files
        for file_path in directory.rglob("*"):
            if should_compress_file(file_path, exclude_extensions, exclude_patterns):
                # Skip files in subdirectories if tar mode is active
                if skip_subdirs and file_path.parent != directory:
                    continue
                files.append(file_path)

    return sorted(set(files))  # Remove duplicates and sort


def find_files_to_decompress(directory: Path, exclude_patterns: List[str] = None) -> List[Path]:
    """
    Recursively find .xz files to decompress.

    Args:
        directory: Root directory to search
        exclude_patterns: Patterns to exclude from path
    """
    if exclude_patterns is None:
        exclude_patterns = []

    files = []

    for file_path in directory.rglob("*.xz"):
        # Skip symlinks
        if file_path.is_symlink():
            continue

        # Skip if not a file
        if not file_path.is_file():
            continue

        # Check exclude patterns
        if exclude_patterns:
            path_str = str(file_path)
            if any(pattern in path_str for pattern in exclude_patterns):
                continue

        files.append(file_path)

    return sorted(set(files))


def get_file_type_stats(files: List[Path]) -> dict:
    """Get statistics about file types in the list."""
    type_stats = {}
    for file_path in files:
        ext = file_path.suffix.lower() or "[no extension]"
        type_stats[ext] = type_stats.get(ext, 0) + 1
    return dict(sorted(type_stats.items(), key=lambda x: x[1], reverse=True))


def print_results_rich(results: List[CompressionResult], directory: Path, operation: str):
    """Print results using Rich formatting."""
    console = Console()

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    # Calculate statistics
    total_original = sum(r.original_size for r in successful)
    total_processed = sum(r.processed_size for r in successful)
    total_duration = sum(r.duration for r in results)
    deleted_count = sum(1 for r in successful if r.original_deleted)
    tarred_count = sum(1 for r in successful if r.was_tarred)

    if operation == "compress":
        space_saved = total_original - total_processed
        avg_ratio = (
            sum((1 - r.processed_size / r.original_size) * 100 for r in successful) / len(successful)
            if successful
            else 0
        )
        operation_emoji = "🗜️"
        operation_name = "Compression"
        size_label = "Compressed"
    else:
        space_saved = total_processed - total_original
        avg_ratio = (
            sum((r.processed_size / r.original_size - 1) * 100 for r in successful) / len(successful)
            if successful
            else 0
        )
        operation_emoji = "📂"
        operation_name = "Decompression"
        size_label = "Decompressed"

    # Create main results table
    table = Table(
        title=f"{operation_emoji} LZMA {operation_name} Results",
        box=box.ROUNDED,
        title_style="bold cyan",
        header_style="bold white",
    )

    table.add_column("File", style="cyan", no_wrap=False)
    table.add_column("Original", justify="right", style="yellow")
    table.add_column(size_label, justify="right", style="green")
    table.add_column("Ratio", justify="right", style="magenta")
    table.add_column("Time", justify="right", style="dim")
    table.add_column("Type", justify="center")
    table.add_column("Status", justify="center")

    # Show top 20 files by original size
    for result in sorted(successful, key=lambda x: x.original_size, reverse=True)[:20]:
        if operation == "compress":
            ratio = (1 - result.processed_size / result.original_size) * 100 if result.original_size > 0 else 0
        else:
            ratio = (result.processed_size / result.original_size - 1) * 100 if result.original_size > 0 else 0

        status = "🗑️ ✅" if result.original_deleted else "✅"
        file_type = "📦 tar" if result.was_tarred else "📄 file"

        # Show relative path if possible
        try:
            file_display = str(result.file_path.relative_to(directory))
        except ValueError:
            file_display = str(result.file_path)

        table.add_row(
            file_display,
            format_size(result.original_size),
            format_size(result.processed_size),
            f"{ratio:.1f}%",
            f"{result.duration:.2f}s",
            file_type,
            status,
        )

    if len(successful) > 20:
        table.add_row(f"... and {len(successful) - 20} more files", "", "", "", "", "", "")

    console.print(table)

    # Failed files
    if failed:
        fail_table = Table(title="❌ Failed Files", box=box.ROUNDED, title_style="bold red")
        fail_table.add_column("File", style="red")
        fail_table.add_column("Error", style="dim")

        for result in failed[:10]:  # Show first 10 failures
            try:
                file_display = str(result.file_path.relative_to(directory))
            except ValueError:
                file_display = str(result.file_path)
            fail_table.add_row(file_display, result.error or "Unknown error")

        if len(failed) > 10:
            fail_table.add_row(f"... and {len(failed) - 10} more failures", "")

        console.print(fail_table)

    # Summary panel
    summary_text = Text()
    summary_text.append(f"📊 {operation_name} Summary\n\n", style="bold cyan")
    summary_text.append(f"📁 Directory: ", style="dim")
    summary_text.append(f"{directory}\n", style="bold white")
    summary_text.append(f"Total files processed: ", style="dim")
    summary_text.append(f"{len(results)}\n", style="bold white")
    summary_text.append(f"✅ Successful: ", style="dim")
    summary_text.append(f"{len(successful)}\n", style="bold green")
    summary_text.append(f"❌ Failed: ", style="dim")
    summary_text.append(f"{len(failed)}\n", style="bold red")

    if tarred_count > 0:
        summary_text.append(f"📦 From tarred directories: ", style="dim")
        summary_text.append(f"{tarred_count}\n", style="bold yellow")

    summary_text.append(f"🗑️  Originals deleted: ", style="dim")
    summary_text.append(f"{deleted_count}\n", style="bold yellow")
    summary_text.append(f"\n💾 Total original size: ", style="dim")
    summary_text.append(f"{format_size(total_original)}\n", style="bold yellow")
    summary_text.append(f"{'🗜️' if operation == 'compress' else '📂'} Total {size_label.lower()} size: ", style="dim")
    summary_text.append(f"{format_size(total_processed)}\n", style="bold green")

    if operation == "compress":
        summary_text.append(f"📈 Average compression: ", style="dim")
        summary_text.append(f"{avg_ratio:.1f}%\n", style="bold magenta")
        summary_text.append(f"🎉 Disk space freed: ", style="dim")
        summary_text.append(f"{format_size(space_saved)} ", style="bold cyan")
    else:
        summary_text.append(f"📈 Average expansion: ", style="dim")
        summary_text.append(f"{avg_ratio:.1f}%\n", style="bold magenta")
        summary_text.append(f"💾 Disk space used: ", style="dim")
        summary_text.append(f"{format_size(space_saved)} ", style="bold cyan")

    if total_original > 0 and operation == "compress":
        summary_text.append(f"({(space_saved / total_original * 100):.1f}%)\n", style="bold cyan")

    summary_text.append(f"⏱️  Total time: ", style="dim")
    summary_text.append(f"{total_duration:.2f}s ", style="bold white")
    if results:
        summary_text.append(f"(avg {total_duration / len(results):.2f}s per file)", style="dim")

    console.print(Panel(summary_text, border_style="cyan"))


def print_results_basic(results: List[CompressionResult], directory: Path, operation: str):
    """Print results using basic formatting."""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    total_original = sum(r.original_size for r in successful)
    total_processed = sum(r.processed_size for r in successful)
    total_duration = sum(r.duration for r in results)
    deleted_count = sum(1 for r in successful if r.original_deleted)
    tarred_count = sum(1 for r in successful if r.was_tarred)

    if operation == "compress":
        space_saved = total_original - total_processed
        avg_ratio = (
            sum((1 - r.processed_size / r.original_size) * 100 for r in successful) / len(successful)
            if successful
            else 0
        )
        operation_name = "Compression"
        size_label = "Compressed"
    else:
        space_saved = total_processed - total_original
        avg_ratio = (
            sum((r.processed_size / r.original_size - 1) * 100 for r in successful) / len(successful)
            if successful
            else 0
        )
        operation_name = "Decompression"
        size_label = "Decompressed"

    print("\n" + "=" * 80)
    print(f"🗜️  LZMA {operation_name} Results")
    print(f"📁 Directory: {directory}")
    print("=" * 80)

    print(f"\n{'File':<40} {'Original':>12} {size_label:>12} {'Ratio':>8} {'Time':>8}")
    print("-" * 80)

    for result in sorted(successful, key=lambda x: x.original_size, reverse=True)[:20]:
        if operation == "compress":
            ratio = (1 - result.processed_size / result.original_size) * 100 if result.original_size > 0 else 0
        else:
            ratio = (result.processed_size / result.original_size - 1) * 100 if result.original_size > 0 else 0

        file_name = result.file_path.name[:37] + "..." if len(result.file_path.name) > 40 else result.file_path.name
        type_indicator = "[tar]" if result.was_tarred else ""
        print(
            f"{file_name:<40} {format_size(result.original_size):>12} {format_size(result.processed_size):>12} {ratio:>7.1f}% {result.duration:>7.2f}s {type_indicator}"
        )

    if len(successful) > 20:
        print(f"... and {len(successful) - 20} more files")

    if failed:
        print(f"\n❌ Failed files ({len(failed)}):")
        for result in failed[:10]:
            print(f"  • {result.file_path.name}: {result.error}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more failures")

    print("\n" + "=" * 80)
    print(f"📊 {operation_name} Summary")
    print("=" * 80)
    print(f"Total files processed: {len(results)}")
    print(f"✅ Successful: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")
    if tarred_count > 0:
        print(f"📦 From tarred directories: {tarred_count}")
    print(f"🗑️  Originals deleted: {deleted_count}")
    print(f"\n💾 Total original size: {format_size(total_original)}")
    print(f"{'🗜️' if operation == 'compress' else '📂'} Total {size_label.lower()} size: {format_size(total_processed)}")

    if operation == "compress":
        print(f"📈 Average compression: {avg_ratio:.1f}%")
        print(
            f"🎉 Disk space freed: {format_size(space_saved)} ({(space_saved / total_original * 100) if total_original > 0 else 0:.1f}%)"
        )
    else:
        print(f"📈 Average expansion: {avg_ratio:.1f}%")
        print(f"💾 Disk space used: {format_size(space_saved)}")

    print(
        f"⏱️  Total time: {total_duration:.2f}s (avg {total_duration / len(results):.2f}s per file)" if results else ""
    )
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="🗜️  Recursively compress/decompress files using LZMA with parallel processing (deletes originals by default)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Compress all files in current directory
  %(prog)s -c                       # Compress all files (explicit)
  %(prog)s -d                       # Decompress all .xz files
  %(prog)s -c -t                    # Tar subdirectories first, then compress
  %(prog)s -c -t /path/to/dir       # Tar subdirs in specific directory
  %(prog)s -c -e txt log csv        # Compress only specific extensions
  %(prog)s -c -p 7 --threads 4      # Custom preset and threads
  %(prog)s -c -p 9 --threads 8      # Maximum compression with 8 threads
  %(prog)s -c --keep-originals      # Keep original files when compressing
  %(prog)s -d --keep-originals      # Keep compressed files when decompressing
  %(prog)s -c --dry-run             # Preview compression without modifying
  %(prog)s --exclude node_modules   # Exclude specific directories
        """,
    )

    # Create mutually exclusive group for compress/decompress
    operation_group = parser.add_mutually_exclusive_group()
    operation_group.add_argument("-c", "--compress", action="store_true", default=True, help="Compress files (default)")
    operation_group.add_argument("-d", "--decompress", action="store_true", help="Decompress .xz files")

    parser.add_argument(
        "-t",
        "--tar-subdirs-first",
        action="store_true",
        help="Tar subdirectories first, then apply LZMA compression on the .tar files (only valid with -c/--compress)",
    )

    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        type=str,
        help="Root directory to process files recursively (default: current directory)",
    )

    parser.add_argument(
        "-e",
        "--extensions",
        nargs="+",
        help="Compress only specific file extensions (e.g., txt log csv). Only valid with -c/--compress.",
    )

    parser.add_argument(
        "-p",
        "--preset",
        type=int,
        default=7,
        choices=range(0, 10),
        help="LZMA compression preset (0-9, default: 7). Higher = better compression but slower.",
    )

    parser.add_argument("--threads", type=int, default=4, help="Number of threads for LZMA compression (default: 4)")

    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=mp.cpu_count(),
        help=f"Number of parallel workers for processing multiple files (default: {mp.cpu_count()})",
    )

    parser.add_argument(
        "--keep-originals", action="store_true", help="Keep original files after processing (default: delete originals)"
    )

    parser.add_argument(
        "--exclude",
        nargs="+",
        default=[],
        help="Directory/file patterns to exclude from processing (e.g., node_modules .git)",
    )

    parser.add_argument("--no-parallel", action="store_true", help="Disable parallel processing")

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be processed without actually modifying files"
    )

    parser.add_argument(
        "--no-skip-compressed",
        action="store_true",
        help="Do not skip already compressed files (dangerous, may double-compress). Only valid with -c/--compress.",
    )

    args = parser.parse_args()

    # Determine operation
    operation = "decompress" if args.decompress else "compress"

    # Validate arguments
    if args.tar_subdirs_first and operation == "decompress":
        print("❌ Error: -t/--tar-subdirs-first is only valid with -c/--compress")
        sys.exit(1)

    if operation == "decompress" and (args.extensions or args.no_skip_compressed):
        print("⚠️  Warning: -e/--extensions and --no-skip-compressed are ignored in decompression mode")

    if operation == "decompress":
        print("ℹ️  Note: -p/--preset and --threads are ignored in decompression mode")

    # Set up exclusion extensions
    if operation == "compress":
        if args.no_skip_compressed:
            exclude_extensions = {".xz"}  # Only skip our own compressed files
            print("⚠️  WARNING: Not skipping already compressed files!")
        else:
            exclude_extensions = EXCLUDED_EXTENSIONS
    else:
        exclude_extensions = set()  # Not used for decompression

    directory = Path(args.directory).resolve()
    if not directory.exists():
        print(f"❌ Error: Directory '{directory}' does not exist")
        sys.exit(1)

    if not directory.is_dir():
        print(f"❌ Error: '{directory}' is not a directory")
        sys.exit(1)

    # Find files to process
    operation_emoji = "🗜️" if operation == "compress" else "📂"
    operation_name = "compression" if operation == "compress" else "decompression"

    print(f"🔍 Scanning directory for {operation_name}: {directory}")

    if operation == "compress":
        if args.tar_subdirs_first:
            print(f"📁 Mode: Tar subdirectories first, then LZMA compression")

            # Process subdirectories with tar + lzma
            tar_results = process_subdirs_with_tar(
                directory,
                preset=args.preset,
                threads=args.threads,
                workers=1 if args.no_parallel else args.workers,
                keep_original=args.keep_originals,
                exclude_patterns=args.exclude,
            )

            # Also process individual files in the root directory
            print(f"\n📁 Processing individual files in root directory...")
            files = find_files_to_compress(
                directory,
                exclude_extensions=exclude_extensions,
                exclude_patterns=args.exclude,
                extensions_filter=args.extensions,
                skip_subdirs=True,  # Skip files in subdirectories (they're being tarred)
            )

            if files:
                print(f"📁 Found {len(files)} individual file(s) in root directory")
                for file_path in files:
                    print(f"  • {file_path.relative_to(directory)}")
            else:
                print(f"📁 No individual files in root directory")

            all_results = tar_results

        else:
            if args.extensions:
                print(f"📁 Mode: Only specified extensions ({', '.join(args.extensions)})")
            else:
                print(f"📁 Mode: ALL files (excluding already compressed formats and symlinks)")

            if args.exclude:
                print(f"🚫 Excluding patterns: {', '.join(args.exclude)}")

            files = find_files_to_compress(
                directory,
                exclude_extensions=exclude_extensions,
                exclude_patterns=args.exclude,
                extensions_filter=args.extensions,
                skip_subdirs=False,
            )
            all_results = []

        if not args.tar_subdirs_first and not files:
            print(f"❌ No files found to compress")
            sys.exit(0)

        if not args.tar_subdirs_first:
            print(f"📁 Found {len(files)} file(s) to compress")

            # Show file type statistics
            type_stats = get_file_type_stats(files)
            if type_stats:
                print(f"📊 File types found:")
                for ext, count in list(type_stats.items())[:10]:
                    print(f"  • {ext}: {count} file(s)")
                if len(type_stats) > 10:
                    print(f"  • ... and {len(type_stats) - 10} more types")

            # Calculate total size
            total_size = sum(f.stat().st_size for f in files)
            print(f"💾 Total size: {format_size(total_size)}")

    else:
        print(f"📁 Mode: Decompressing .xz files")

        if args.exclude:
            print(f"🚫 Excluding patterns: {', '.join(args.exclude)}")

        files = find_files_to_decompress(directory, exclude_patterns=args.exclude)

        if not files:
            print(f"❌ No .xz files found to decompress")
            sys.exit(0)

        print(f"📁 Found {len(files)} .xz file(s) to decompress")

        # Calculate total size
        total_size = sum(f.stat().st_size for f in files)
        print(f"💾 Total compressed size: {format_size(total_size)}")

    if args.dry_run:
        if args.tar_subdirs_first:
            print(f"\n🔍 DRY RUN - Would tar subdirectories and compress them with LZMA")
        else:
            print(f"\n🔍 DRY RUN - Would {operation} {len(files)} files ({format_size(total_size)})")
        print("No files were modified.")
        return

    if not args.keep_originals:
        if operation == "compress":
            if args.tar_subdirs_first:
                print("⚠️  Subdirectories will be tarred and originals DELETED (use --keep-originals to preserve)")
            else:
                print("⚠️  Originals will be DELETED after compression (use --keep-originals to preserve)")
        else:
            print("⚠️  Compressed .xz files will be DELETED after decompression (use --keep-originals to preserve)")

    if operation == "compress":
        print(f"🎯 Compression preset: {args.preset}/9")
        print(f"🧵 LZMA threads: {args.threads}")

    # Adjust workers
    workers = 1 if args.no_parallel else min(args.workers, len(files) if not args.tar_subdirs_first else args.workers)
    if not args.tar_subdirs_first:
        print(f"👷 Workers: {workers}")
    print()

    results = []

    if args.tar_subdirs_first:
        # Results already collected from tar processing
        results = all_results

        # Now process individual files if any
        if files:
            print(f"🔄 Compressing individual files...")

            if RICH_AVAILABLE:
                console = Console()

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task("🔄 Compressing individual files", total=len(files))

                    if workers > 1 and len(files) > 1:
                        with ProcessPoolExecutor(max_workers=workers) as executor:
                            futures = {}
                            for file_path in files:
                                output_path = file_path.with_suffix(file_path.suffix + ".xz")
                                future = executor.submit(
                                    compress_file_streaming,
                                    file_path,
                                    output_path,
                                    args.preset,
                                    args.threads,
                                    1024 * 1024,
                                    args.keep_originals,
                                )
                                futures[future] = file_path

                            for future in as_completed(futures):
                                result = future.result()
                                results.append(result)
                                progress.advance(task)
                    else:
                        for file_path in files:
                            output_path = file_path.with_suffix(file_path.suffix + ".xz")
                            result = compress_file_streaming(
                                file_path, output_path, args.preset, args.threads, 1024 * 1024, args.keep_originals
                            )
                            results.append(result)
                            progress.advance(task)
            else:
                for i, file_path in enumerate(files, 1):
                    output_path = file_path.with_suffix(file_path.suffix + ".xz")
                    result = compress_file_streaming(
                        file_path, output_path, args.preset, args.threads, 1024 * 1024, args.keep_originals
                    )
                    results.append(result)
                    status = "🗑️ ✅" if result.success and result.original_deleted else "✅" if result.success else "❌"
                    print(f"  [{i}/{len(files)}] {file_path.name} - {status}")

    elif not args.tar_subdirs_first:
        if RICH_AVAILABLE:
            console = Console()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"🔄 {operation_name.capitalize()} files", total=len(files))

                if workers > 1 and len(files) > 1:
                    with ProcessPoolExecutor(max_workers=workers) as executor:
                        futures = {}
                        for file_path in files:
                            if operation == "compress":
                                output_path = file_path.with_suffix(file_path.suffix + ".xz")
                                future = executor.submit(
                                    compress_file_streaming,
                                    file_path,
                                    output_path,
                                    args.preset,
                                    args.threads,
                                    1024 * 1024,
                                    args.keep_originals,
                                )
                            else:
                                output_path = file_path.with_suffix("")  # Remove .xz extension
                                future = executor.submit(
                                    decompress_file_streaming, file_path, output_path, 1024 * 1024, args.keep_originals
                                )
                            futures[future] = file_path

                        for future in as_completed(futures):
                            result = future.result()
                            results.append(result)
                            progress.advance(task)
                else:
                    for file_path in files:
                        if operation == "compress":
                            output_path = file_path.with_suffix(file_path.suffix + ".xz")
                            result = compress_file_streaming(
                                file_path, output_path, args.preset, args.threads, 1024 * 1024, args.keep_originals
                            )
                        else:
                            output_path = file_path.with_suffix("")
                            result = decompress_file_streaming(file_path, output_path, 1024 * 1024, args.keep_originals)
                        results.append(result)
                        progress.advance(task)
        else:
            # Basic progress without Rich
            print(f"🔄 {operation_name.capitalize()} files...")

            if workers > 1 and len(files) > 1:
                with ProcessPoolExecutor(max_workers=workers) as executor:
                    futures = {}
                    for file_path in files:
                        if operation == "compress":
                            output_path = file_path.with_suffix(file_path.suffix + ".xz")
                            future = executor.submit(
                                compress_file_streaming,
                                file_path,
                                output_path,
                                args.preset,
                                args.threads,
                                1024 * 1024,
                                args.keep_originals,
                            )
                        else:
                            output_path = file_path.with_suffix("")
                            future = executor.submit(
                                decompress_file_streaming, file_path, output_path, 1024 * 1024, args.keep_originals
                            )
                        futures[future] = file_path

                    for i, future in enumerate(as_completed(futures), 1):
                        result = future.result()
                        results.append(result)
                        status = (
                            "🗑️ ✅" if result.success and result.original_deleted else "✅" if result.success else "❌"
                        )
                        print(f"  [{i}/{len(files)}] {result.file_path.name} - {status}")
            else:
                for i, file_path in enumerate(files, 1):
                    if operation == "compress":
                        output_path = file_path.with_suffix(file_path.suffix + ".xz")
                        result = compress_file_streaming(
                            file_path, output_path, args.preset, args.threads, 1024 * 1024, args.keep_originals
                        )
                    else:
                        output_path = file_path.with_suffix("")
                        result = decompress_file_streaming(file_path, output_path, 1024 * 1024, args.keep_originals)
                    results.append(result)
                    status = "🗑️ ✅" if result.success and result.original_deleted else "✅" if result.success else "❌"
                    print(f"  [{i}/{len(files)}] {file_path.name} - {status}")

    # Print results
    if results:
        if RICH_AVAILABLE:
            print_results_rich(results, directory, operation)
        else:
            print_results_basic(results, directory, operation)


if __name__ == "__main__":
    main()
