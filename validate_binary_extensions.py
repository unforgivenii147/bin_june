#!/data/data/com.termux/files/usr/bin/env python


"""
Sanity check script to validate binary file extensions.
Traverses the filesystem to find files with extensions in BIN_EXT,
verifies they are actually binary files, and reports mismatches.
Uses memory-efficient os.walk traversal with progress reporting
and optimized filesystem walking strategies.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import sys
from functools import lru_cache
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Iterator

from dh import BIN_EXT

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class OptimizedWalker:
    def __init__(self, skip_symlinks: bool = True, skip_mount_points: bool = True):
        self.skip_symlinks = skip_symlinks
        self.skip_mount_points = skip_mount_points
        self.visited_inodes = set()
        self.root_dev = None
        self._is_symlink = os.path.islink
        self._stat = os.stat
        self._scandir = os.scandir if hasattr(os, "scandir") else None

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_extensions_lower(extensions: tuple) -> set:
        return {ext.lower() for ext in extensions}

    def walk(self, root_dir: str, extensions: set[str], progress_callback=None) -> Iterator[Path]:
        extensions_lower = self._get_extensions_lower(tuple(extensions))
        file_count = 0
        if self.skip_mount_points:
            try:
                self.root_dev = self._stat(root_dir).st_dev
            except OSError:
                self.root_dev = None
        try:
            yield from self._walk_recursive(root_dir, extensions_lower, progress_callback, file_count)
        except KeyboardInterrupt:
            logger.info("Traversal interrupted by user")
            raise

    def _walk_recursive(
        self, current_dir: str, extensions_lower: set[str], progress_callback, file_count: int
    ) -> Iterator[Path]:
        if self.skip_symlinks:
            try:
                dir_stat = self._stat(current_dir)
                dir_inode = (dir_stat.st_dev, dir_stat.st_ino)
                if dir_inode in self.visited_inodes:
                    return
                self.visited_inodes.add(dir_inode)
                if self.skip_mount_points and self.root_dev is not None:
                    if dir_stat.st_dev != self.root_dev:
                        return
            except (OSError, FileNotFoundError):
                return
        try:
            if self._scandir:
                with self._scandir(current_dir) as entries:
                    directories = []
                    for entry in entries:
                        try:
                            if entry.is_file():
                                if entry.name.lower().endswith(tuple(extensions_lower)):
                                    file_count += 1
                                    if progress_callback and file_count % 500 == 0:
                                        progress_callback(current_dir, file_count)
                                    yield Path(entry.path)
                            elif entry.is_dir() and (not self._is_symlink(entry.path)):
                                directories.append(entry.path)
                        except (OSError, FileNotFoundError):
                            continue
                    for dir_path in directories:
                        yield from self._walk_recursive(dir_path, extensions_lower, progress_callback, file_count)
            else:
                for entry in os.listdir(current_dir):
                    full_path = os.path.join(current_dir, entry)
                    try:
                        if os.path.isfile(full_path):
                            if entry.lower().endswith(tuple(extensions_lower)):
                                file_count += 1
                                if progress_callback and file_count % 500 == 0:
                                    progress_callback(current_dir, file_count)
                                yield Path(full_path)
                        elif os.path.isdir(full_path) and (not self._is_symlink(full_path)):
                            yield from self._walk_recursive(full_path, extensions_lower, progress_callback, file_count)
                    except (OSError, FileNotFoundError):
                        continue
        except PermissionError:
            logger.debug(f"Permission denied: {current_dir}")
        except OSError as e:
            logger.debug(f"Error accessing {current_dir}: {e}")


class SpinnerProgressReporter:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.last_count = 0
        self.spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_index = 0

    def __call__(self, current_path: str, file_count: int):
        if not self.verbose:
            return
        if file_count - self.last_count >= 500:
            self.last_count = file_count
            self.spinner_index = (self.spinner_index + 1) % len(self.spinner)
            path_display = current_path[:60] + "..." if len(current_path) > 60 else current_path
            msg = f"\r{self.spinner[self.spinner_index]} Files: {file_count:8d} | {path_display}"
            print(msg, end="", flush=True)


def is_binary_file(file_path: Path) -> bool | None:
    try:
        if file_path.stat().st_size == 0:
            return None
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
        if not chunk:
            return None
        if b"\x00" in chunk:
            return True
        non_text_chars = 0
        for byte in chunk:
            if byte < 32 and byte not in (9, 10, 13):
                non_text_chars += 1
                if non_text_chars > len(chunk) * 0.3:
                    return True
        try:
            chunk.decode("utf-8")
            return False
        except UnicodeDecodeError:
            try:
                decoded = chunk.decode("latin-1")
                control_chars = sum(1 for c in decoded if ord(c) < 32 and c not in "\t\n\r")
                return control_chars > len(decoded) * 0.3
            except Exception:
                return True
    except (OSError, PermissionError):
        return None


def check_file(file_path: Path) -> tuple[Path, str, bool | None, str]:
    try:
        extension = file_path.suffix.lower()
        is_binary = is_binary_file(file_path)
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "unknown"
        return (file_path, extension, is_binary, mime_type)
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return (file_path, file_path.suffix.lower(), None, "error")


def validate_extensions(
    root_dir: str = "/", num_workers: int | None = None, verbose: bool = True, skip_mount_points: bool = True
) -> dict:
    if num_workers is None:
        num_workers = max(1, cpu_count() - 1)
    root_path = Path(root_dir)
    if not root_path.exists():
        logger.error(f"Root directory {root_dir} does not exist")
        return {}
    logger.info(f"Starting optimized filesystem traversal from {root_dir}...")
    logger.info(f"Looking for extensions: {sorted(BIN_EXT)}")
    logger.info(f"Using {num_workers} worker processes")
    if skip_mount_points:
        logger.info("Skipping different filesystems/mount points")
    print()
    walker = OptimizedWalker(skip_symlinks=True, skip_mount_points=skip_mount_points)
    progress = SpinnerProgressReporter(verbose=verbose)
    matching_files = list(walker.walk(root_dir, BIN_EXT, progress_callback=progress))
    print()
    if not matching_files:
        logger.warning("No files found with specified extensions")
        return {
            "total_files": 0,
            "binary_files": 0,
            "text_files": 0,
            "access_errors": 0,
            "mismatches": [],
            "by_extension": {},
        }
    logger.info(f"Found {len(matching_files)} files with target extensions")
    logger.info("Checking file types (parallel processing)...")
    with Pool(num_workers) as pool:
        results = pool.map(check_file, matching_files, chunksize=100)
    binary_count = 0
    text_count = 0
    error_count = 0
    mismatches = []
    by_extension = {}
    for file_path, ext, is_binary, mime_type in results:
        if ext not in by_extension:
            by_extension[ext] = {"binary": 0, "text": 0, "error": 0, "files": []}
        by_extension[ext]["files"].append({"path": str(file_path), "is_binary": is_binary, "mime_type": mime_type})
        if is_binary is True:
            binary_count += 1
            by_extension[ext]["binary"] += 1
        elif is_binary is False:
            text_count += 1
            by_extension[ext]["text"] += 1
            mismatches.append({"path": str(file_path), "extension": ext, "mime_type": mime_type})
        else:
            error_count += 1
            by_extension[ext]["error"] += 1
    return {
        "total_files": len(matching_files),
        "binary_files": binary_count,
        "text_files": text_count,
        "access_errors": error_count,
        "mismatches": mismatches,
        "by_extension": by_extension,
    }


def print_report(results: dict):
    print("\n" + "=" * 80)
    print("BINARY EXTENSION VALIDATION REPORT")
    print("=" * 80)
    print("\nSummary:")
    print(f"  Total files found:    {results['total_files']}")
    print(f"  Actual binary files:  {results['binary_files']}")
    print(f"  Text files:           {results['text_files']}")
    print(f"  Access errors:        {results['access_errors']}")
    if results.get("mismatches"):
        print(
            f"\n⚠️  MISMATCHES FOUND: {len(results['mismatches'])} files with binary extension are actually TEXT files"
        )
        print("-" * 80)
        for i, mismatch in enumerate(results["mismatches"][:20], 1):
            print(f"  {i}. {mismatch['path']}")
            print(f"     └─ Extension: {mismatch['extension']} | MIME: {mismatch['mime_type']}")
        if len(results["mismatches"]) > 20:
            print(f"  ... and {len(results['mismatches']) - 20} more")
    else:
        print("\n✓ No mismatches found! All files match their extensions.")
    print("\nBreakdown by extension:")
    print("-" * 80)
    for ext, stats in sorted(results["by_extension"].items()):
        print(f"  {ext:12} - Binary: {stats['binary']:6}  Text: {stats['text']:6}  Errors: {stats['error']:6}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    root_dir = "/data/data/com.termux"
    skip_mounts = True
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    if len(sys.argv) > 2:
        skip_mounts = sys.argv[2].lower() in ("true", "1", "yes")
    try:
        results = validate_extensions(root_dir, verbose=True, skip_mount_points=skip_mounts)
        print_report(results)
        sys.exit(1 if results.get("mismatches") else 0)
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation stopped by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Validation failed")
        sys.exit(1)
