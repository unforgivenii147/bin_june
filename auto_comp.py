#!/data/data/com.termux/files/usr/bin/python
"""
Universal compression utility with automatic best-compressor selection.

Compresses files/directories using multiple algorithms and retains
only the best result based on compression ratio.
"""

import bz2
import gzip
import lzma
import os
import shutil
import sys
import tarfile
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import blosc2
import brotli
import lz4.frame
import py7zr
import zstandard as zstd

# Type aliases
CompressorFunc = Callable[[bytes], bytes]

# Constants
COMPRESSION_LEVEL_MAX: Final[int] = 9
ZSTD_LEVEL_MAX: Final[int] = 21
BROTLI_QUALITY_MAX: Final[int] = 11
REPORT_WIDTH: Final[int] = 70

# Compression configurations
COMPRESSORS: Final[dict[str, tuple[CompressorFunc, str]]] = {
    "brotli": (lambda d: brotli.compress(d, quality=BROTLI_QUALITY_MAX), ".br"),
    "zstd": (lambda d: zstd.ZstdCompressor(level=ZSTD_LEVEL_MAX).compress(d), ".zst"),
    "xz": (lambda d: lzma.compress(d, preset=COMPRESSION_LEVEL_MAX, format=lzma.FORMAT_XZ), ".xz"),
    "bz2": (lambda d: bz2.compress(d, compresslevel=COMPRESSION_LEVEL_MAX), ".bz2"),
    "gzip": (lambda d: gzip.compress(d, compresslevel=COMPRESSION_LEVEL_MAX), ".gz"),
    "lz4": (
        lambda d: lz4.frame.compress(
            d,
            compression_context=lz4.frame.create_compression_context(lz4.frame.COMPRESSIONLEVEL_MAX),
        ),
        ".lz4",
    ),
    "blosc2": (
        lambda d: blosc2.compress(d, codec=blosc2.Codec.zstd, clevel=COMPRESSION_LEVEL_MAX),
        ".blosc2",
    ),
}


@dataclass(slots=True, frozen=True)
class CompressionResult:
    """Immutable result of a compression operation."""

    name: str
    size: int
    ratio: float
    time: float
    path: Path
    original_size: int = field(repr=False)

    @property
    def saved_bytes(self) -> int:
        """Calculate bytes saved compared to original."""
        return self.original_size - self.size

    @property
    def savings_percent(self) -> float:
        """Calculate savings as percentage."""
        return (self.saved_bytes / self.original_size) * 100


class CompressionManager:
    """Manages compression operations across multiple algorithms."""

    __slots__ = ("output_dir", "temp_dir")

    def __init__(self, output_dir: str | Path = ".", *, keep_temp: bool = False) -> None:
        """Initialize compression manager.

        Args:
            output_dir: Directory for compressed output files.
            keep_temp: If True, keep temporary files after compression.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = tempfile.mkdtemp(prefix="compress_")

    def __del__(self) -> None:
        """Cleanup temporary directory."""
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    @staticmethod
    def prepare_input(target_path: str | Path) -> tuple[bytes, str]:
        """Prepare input data for compression.

        Args:
            target_path: Path to file or directory.

        Returns:
            Tuple of (data_bytes, base_name).

        Raises:
            ValueError: If path is neither file nor directory.
            FileNotFoundError: If path doesn't exist.
        """
        target = Path(target_path)

        if not target.exists():
            raise FileNotFoundError(f"Target not found: {target_path}")

        if target.is_file():
            data = target.read_bytes()
            return data, target.name

        if target.is_dir():
            # Create temporary tar archive
            tar_name = f"{target.name}.tar"
            tar_path = Path(tempfile.gettempdir()) / tar_name

            try:
                with tarfile.open(tar_path, "w") as tar:
                    tar.add(target, arcname=target.name)

                data = tar_path.read_bytes()
                return data, tar_name
            finally:
                # Clean up temporary tar
                try:
                    tar_path.unlink(missing_ok=True)
                except Exception:
                    pass

        raise ValueError(f"Target is neither file nor directory: {target_path}")

    def compress_single(
        self,
        name: str,
        compress_func: CompressorFunc,
        extension: str,
        data: bytes,
        base_name: str,
    ) -> CompressionResult | None:
        """Compress data using a single algorithm.

        Args:
            name: Algorithm name.
            compress_func: Compression function.
            extension: File extension for output.
            data: Data to compress.
            base_name: Base name for output file.

        Returns:
            CompressionResult or None if compression failed.
        """
        output_path = self.output_dir / f"{base_name}{extension}"

        try:
            start_time = time.perf_counter()
            compressed = compress_func(data)
            elapsed = time.perf_counter() - start_time

            output_path.write_bytes(compressed)

            comp_size = len(compressed)
            ratio = comp_size / len(data)

            return CompressionResult(
                name=name,
                size=comp_size,
                ratio=ratio,
                time=elapsed,
                path=output_path,
                original_size=len(data),
            )

        except Exception as e:
            print(f"✗ {name:10} | Error: {e}")
            try:
                output_path.unlink(missing_ok=True)
            except Exception:
                pass
            return None

    def compress_7z(self, data: bytes, base_name: str) -> CompressionResult | None:
        """Compress data using 7z format.

        Args:
            data: Data to compress.
            base_name: Base name for output file.

        Returns:
            CompressionResult or None if compression failed.
        """
        output_path = self.output_dir / f"{base_name}.7z"

        try:
            # Create temporary file for 7z compression
            temp_file = Path(self.temp_dir) / base_name
            temp_file.write_bytes(data)

            start_time = time.perf_counter()

            with py7zr.SevenZipFile(output_path, "w") as archive:
                archive.write(temp_file, arcname=base_name)

            elapsed = time.perf_counter() - start_time
            comp_size = output_path.stat().st_size
            ratio = comp_size / len(data)

            return CompressionResult(
                name="7z",
                size=comp_size,
                ratio=ratio,
                time=elapsed,
                path=output_path,
                original_size=len(data),
            )

        except Exception as e:
            print(f"✗ {'7z':10} | Error: {e}")
            try:
                output_path.unlink(missing_ok=True)
            except Exception:
                pass
            return None

        finally:
            # Clean up temporary file
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass

    def compress_all(self, data: bytes, base_name: str) -> list[CompressionResult]:
        """Compress data using all available algorithms.

        Args:
            data: Data to compress.
            base_name: Base name for output files.

        Returns:
            Sorted list of CompressionResults (best ratio first).
        """
        results: list[CompressionResult] = []
        original_size = len(data)

        print(f"Original size: {original_size:,} bytes\n")
        print("COMPRESSION PROGRESS:")
        print("-" * REPORT_WIDTH)

        # Compress with standard algorithms
        for name, (compress_func, extension) in COMPRESSORS.items():
            result = self.compress_single(name, compress_func, extension, data, base_name)
            if result:
                results.append(result)
                print(
                    f"✓ {result.name:10} | "
                    f"Size: {result.size:12,} | "
                    f"Ratio: {result.ratio:.4f} | "
                    f"Time: {result.time:.3f}s"
                )

        # Compress with 7z (handled separately due to file requirement)
        result_7z = self.compress_7z(data, base_name)
        if result_7z:
            results.append(result_7z)
            print(
                f"✓ {result_7z.name:10} | "
                f"Size: {result_7z.size:12,} | "
                f"Ratio: {result_7z.ratio:.4f} | "
                f"Time: {result_7z.time:.3f}s"
            )

        return sorted(results, key=lambda x: x.ratio)

    @staticmethod
    def cleanup_results(results: list[CompressionResult], keep_best: bool = True) -> CompressionResult | None:
        """Clean up compression results, keeping only the best.

        Args:
            results: List of compression results.
            keep_best: If True, keep only the best result.

        Returns:
            The best CompressionResult or None if no results.
        """
        if not results:
            return None

        best = results[0]

        if keep_best:
            print(f"\n✓ Keeping best: {best.name} ({best.path})")

            # Delete other results
            for result in results[1:]:
                try:
                    result.path.unlink(missing_ok=True)
                    print(f"✗ Deleted: {result.name}")
                except Exception as e:
                    print(f"⚠ Failed to delete {result.name}: {e}")

        return best


def print_report(results: list[CompressionResult], original_size: int) -> None:
    """Print compression results report.

    Args:
        results: Sorted list of compression results.
        original_size: Original data size in bytes.
    """
    print("\n" + "=" * REPORT_WIDTH)
    print("COMPRESSION RESULTS")
    print("=" * REPORT_WIDTH)

    if not results:
        print("No successful compressions.")
        return

    # Print top 3 results
    print("\nTOP RESULTS:")
    print("-" * REPORT_WIDTH)

    for i, result in enumerate(results[:3], 1):
        print(
            f"{i}. {result.name:10} | "
            f"Size: {result.size:12,} | "
            f"Ratio: {result.ratio:.4f} | "
            f"Saved: {result.saved_bytes:12,} bytes | "
            f"Savings: {result.savings_percent:.1f}%"
        )

    # Print all results table
    print("\nALL RESULTS:")
    print("-" * REPORT_WIDTH)
    print(f"{'Name':<10} {'Size':>12} {'Ratio':>8} {'Saved':>12} {'Time':>8}")
    print("-" * REPORT_WIDTH)

    for result in results:
        print(
            f"{result.name:<10} {result.size:>12,} {result.ratio:>8.4f} {result.saved_bytes:>12,} {result.time:>7.3f}s"
        )


def main() -> None:
    """Main entry point for the compression utility."""
    if len(sys.argv) < 2:
        print("Usage: python script.py <file_or_directory> [output_directory]")
        print("\nCompresses the target using multiple algorithms and keeps the best result.")
        sys.exit(1)

    target = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    if not os.path.exists(target):
        print(f"Error: Target not found: {target}")
        sys.exit(1)

    print(f"📦 Compressing: {target}")
    print(f"📁 Output directory: {output_dir}\n")

    try:
        # Prepare input data
        manager = CompressionManager(output_dir=output_dir)
        data, base_name = manager.prepare_input(target)

        # Compress with all algorithms
        results = manager.compress_all(data, base_name)

        # Print report
        print_report(results, len(data))

        # Keep only the best result
        manager.cleanup_results(results, keep_best=True)

    except KeyboardInterrupt:
        print("\n\n⚠ Compression interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
