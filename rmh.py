#!/data/data/com.termux/files/usr/bin/env python
"""
Safely remove single-line and multi-line comments from C/C++ source files.

Features:
- Accept multiple files/folders as input (or process current directory recursively)
- Recursive directory traversal using pathlib
- Parallel processing with multiprocessing
- Handles both // (single-line) and /* */ (multi-line) comments
- Preserves string literals and character literals
- Updates files in-place with backup creation
- Progress tracking with tqdm
- Detailed logging of changes
- Reports disk space freed at the end
"""

import re
import sys
import os
from pathlib import Path
from typing import Tuple, Optional, List
from dataclasses import dataclass
from multiprocessing import Pool, cpu_count
from loguru import logger
from tqdm import tqdm
from datetime import datetime


@dataclass
class ProcessResult:
    """Result of processing a single file."""

    path: Path
    success: bool
    original_lines: int
    final_lines: int
    comments_removed: int
    original_size: int
    final_size: int
    backup_size: int
    error: Optional[str] = None

    @property
    def space_freed(self) -> int:
        """Calculate space freed (original - final size)."""
        return max(0, self.original_size - self.final_size)

    @property
    def total_space_used(self) -> int:
        """Calculate total space used (final + backup)."""
        return self.final_size + self.backup_size


class CommentRemover:
    STRING_PATTERN = r"""(?:"(?:\.|[^"\])*"|'(?:\.|[^'\])*')"""

    SINGLE_COMMENT_PATTERN = r"//.*?(?=\n|$)"

    MULTI_COMMENT_PATTERN = r"/\*.*?\*/"

    def __init__(self):
        """Initialize the comment remover with compiled regex patterns."""
        self.string_regex = re.compile(self.STRING_PATTERN)
        self.single_comment_regex = re.compile(self.SINGLE_COMMENT_PATTERN)
        self.multi_comment_regex = re.compile(self.MULTI_COMMENT_PATTERN, re.DOTALL)

    def _protect_strings(self, text: str) -> Tuple[str, dict]:
        """
        Replace string literals with placeholders to protect them from comment removal.

        Args:
            text: Source code text

        Returns:
            Tuple of (text with protected strings, mapping of placeholders to originals)
        """
        protected_strings = {}
        placeholder_counter = [0]

        def replace_string(match):
            placeholder = f"__STRING_PLACEHOLDER_{placeholder_counter[0]}__"
            protected_strings[placeholder] = match.group(0)
            placeholder_counter[0] += 1
            return placeholder

        protected_text = self.string_regex.sub(replace_string, text)
        return protected_text, protected_strings

    def _restore_strings(self, text: str, protected_strings: dict) -> str:
        """
        Restore protected string literals.

        Args:
            text: Text with placeholders
            protected_strings: Mapping of placeholders to original strings

        Returns:
            Text with strings restored
        """
        for placeholder, original in protected_strings.items():
            text = text.replace(placeholder, original)
        return text

    def remove_comments(self, text: str) -> Tuple[str, int]:
        """
        Remove comments from C/C++ source code.

        Args:
            text: Source code text

        Returns:
            Tuple of (cleaned text, number of comments removed)
        """
        # Protect string literals
        protected_text, protected_strings = self._protect_strings(text)

        # Count comments before removal
        single_count = len(self.single_comment_regex.findall(protected_text))
        multi_count = len(self.multi_comment_regex.findall(protected_text))
        total_comments = single_count + multi_count

        # Remove single-line comments
        protected_text = self.single_comment_regex.sub("", protected_text)

        # Remove multi-line comments
        protected_text = self.multi_comment_regex.sub("", protected_text)

        # Clean up extra whitespace (remove lines that became empty)
        lines = protected_text.split("\n")
        cleaned_lines = []
        for line in lines:
            # Remove trailing whitespace but preserve at least empty lines
            stripped = line.rstrip()
            cleaned_lines.append(stripped)

        # Remove consecutive empty lines (keep max 1)
        final_lines = []
        prev_empty = False
        for line in cleaned_lines:
            if not line.strip():
                if not prev_empty:
                    final_lines.append(line)
                prev_empty = True
            else:
                final_lines.append(line)
                prev_empty = False

        protected_text = "\n".join(final_lines)

        # Restore string literals
        cleaned_text = self._restore_strings(protected_text, protected_strings)

        return cleaned_text, total_comments

    def process_file(self, path: Path) -> ProcessResult:
        """
        Process a single C/C++ file to remove comments.

        Args:
            path: Path to the file to process

        Returns:
            ProcessResult with details of the operation
        """
        try:
            # Ensure absolute path
            path = path.resolve()

            # Read original content
            original_content = path.read_text(encoding="utf-8")
            original_lines = len(original_content.split("\n"))
            original_size = len(original_content.encode("utf-8"))

            # Remove comments
            cleaned_content, comments_removed = self.remove_comments(original_content)
            final_lines = len(cleaned_content.split("\n"))
            final_size = len(cleaned_content.encode("utf-8"))

            # Create backup before modifying
            #            backup_path = path.with_suffix(path.suffix + '.bak')
            #            backup_path.write_text(original_content, encoding="utf-8")
            backup_size = len(original_content.encode("utf-8"))

            # Write cleaned content back to file
            path.write_text(cleaned_content, encoding="utf-8")

            return ProcessResult(
                path=path,
                success=True,
                original_lines=original_lines,
                final_lines=final_lines,
                comments_removed=comments_removed,
                original_size=original_size,
                final_size=final_size,
                backup_size=backup_size,
            )

        except UnicodeDecodeError as e:
            return ProcessResult(
                path=path,
                success=False,
                original_lines=0,
                final_lines=0,
                comments_removed=0,
                original_size=0,
                final_size=0,
                backup_size=0,
                error=f"Encoding error: {e}",
            )
        except Exception as e:
            return ProcessResult(
                path=path,
                success=False,
                original_lines=0,
                final_lines=0,
                comments_removed=0,
                original_size=0,
                final_size=0,
                backup_size=0,
                error=f"Processing error: {e}",
            )


def find_source_files(root_dir: Path) -> List[Path]:
    """
    Find all C/C++ source files recursively.

    Args:
        root_dir: Root directory to search

    Returns:
        List of Path objects for found files
    """
    extensions = {".h", ".hpp", ".c", ".cpp", ".cc", ".cxx", ".hxx"}
    files = []

    if root_dir.is_file():
        # If it's a file, check if it has a valid extension
        if root_dir.suffix in extensions:
            files.append(root_dir)
    else:
        # If it's a directory, search recursively
        for ext in extensions:
            files.extend(root_dir.rglob(f"*{ext}"))

    return sorted(files)


def collect_source_files(targets: List[str]) -> List[Path]:
    """
    Collect all source files from multiple targets (files or directories).

    Args:
        targets: List of file/directory paths

    Returns:
        List of unique Path objects for all found files
    """
    all_files = set()

    for target in targets:
        path = Path(target).resolve()

        if not path.exists():
            logger.warning(f"Path not found: {target}")
            continue

        found_files = find_source_files(path)
        all_files.update(found_files)

    return sorted(list(all_files))


def process_files_parallel(paths: List[Path], num_workers: int = None) -> List[ProcessResult]:
    """
    Process multiple files in parallel.

    Args:
        paths: List of file paths to process
        num_workers: Number of parallel workers (default: CPU count)

    Returns:
        List of ProcessResult objects
    """
    num_workers = num_workers or cpu_count()
    remover = CommentRemover()

    with Pool(num_workers) as pool:
        results = list(
            tqdm(
                pool.imap_unordered(remover.process_file, paths),
                total=len(paths),
                desc="Processing files",
                unit="file",
            )
        )

    return results


def _safe_relative_path(path: Path, root_dir: Path) -> str:
    """
    Safely get relative path, handling both absolute and relative paths.

    Args:
        path: The file path
        root_dir: The root directory

    Returns:
        Relative path string or just the file name if relative_to fails
    """
    try:
        # Try to make both absolute first
        abs_file = path.resolve()
        abs_root = root_dir.resolve()
        return str(abs_file.relative_to(abs_root))
    except ValueError:
        # If not in subpath, just return the name or str representation
        return str(path)


def _format_bytes(bytes_val: int) -> str:
    """
    Format bytes as human-readable string.

    Args:
        bytes_val: Number of bytes

    Returns:
        Formatted string (B, KB, MB, GB)
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} TB"


def print_summary(results: List[ProcessResult], targets: List[Path]) -> None:
    """
    Print summary of processing results with disk space information.

    Args:
        results: List of ProcessResult objects
        targets: List of target directories/files
    """
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    total_comments = sum(r.comments_removed for r in successful)
    total_lines_removed = sum(r.original_lines - r.final_lines for r in successful)
    total_space_freed = sum(r.space_freed for r in successful)
    total_final_size = sum(r.final_size for r in successful)
    total_backup_size = sum(r.backup_size for r in successful)
    total_space_used = total_final_size + total_backup_size

    logger.info("=" * 70)
    logger.info("Processing Summary:")
    logger.info(f"  Files processed: {len(results)}")
    logger.info(f"  Successful: {len(successful)}")
    logger.info(f"  Failed: {len(failed)}")
    logger.info(f"  Total comments removed: {total_comments}")
    logger.info(f"  Total lines removed: {total_lines_removed}")
    logger.info("=" * 70)
    logger.info("Disk Space Summary:")
    logger.info(f"  Space freed: {_format_bytes(total_space_freed)}")
    logger.info(f"  Final file size: {_format_bytes(total_final_size)}")
    logger.info(f"  Backup files size: {_format_bytes(total_backup_size)}")
    logger.info(f"  Total space used: {_format_bytes(total_space_used)}")
    logger.info("=" * 70)

    if successful:
        logger.info("Successful files:")
        for result in successful:
            logger.info(
                f"  {result.path.name}: "
                f"{result.comments_removed} comments, "
                f"{result.original_lines - result.final_lines} lines removed, "
                f"freed {_format_bytes(result.space_freed)}"
            )

    if failed:
        logger.warning("Failed files:")
        for result in failed:
            logger.warning(f"  {result.path.name}: {result.error}")


def main(
    targets: Optional[List[str]] = None,
    num_workers: int = None,
    keep_backups: bool = True,
    dry_run: bool = False,
) -> int:
    """
    Main function to remove comments from C/C++ files.

    Args:
        targets: List of file/directory paths (default: current directory)
        num_workers: Number of parallel workers (default: CPU count)
        keep_backups: Whether to keep .bak files (default: True)
        dry_run: Preview changes without modifying files (default: False)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # If no targets provided, use current directory
    if not targets:
        targets = ["."]

    # Resolve target paths
    target_paths = []
    for target in targets:
        path = Path(target).resolve()
        if not path.exists():
            logger.error(f"Path not found: {target}")
            return 1
        target_paths.append(path)

    # Find source files
    logger.info(f"Scanning for C/C++ files...")
    logger.info(f"Targets: {', '.join(str(p) for p in target_paths)}")
    source_files = collect_source_files(targets)

    if not source_files:
        logger.warning("No C/C++ source files found.")
        return 0

    logger.info(f"Found {len(source_files)} source files")
    logger.info(f"File types: .h, .hpp, .c, .cpp, .cc, .cxx, .hxx")

    if dry_run:
        logger.info("DRY RUN MODE: No files will be modified")
        # Still process but don't write
        remover = CommentRemover()
        total_preview_freed = 0
        for path in source_files[:5]:  # Show sample
            try:
                content = path.read_text(encoding="utf-8")
                cleaned, comments = remover.remove_comments(content)
                original_size = len(content.encode("utf-8"))
                final_size = len(cleaned.encode("utf-8"))
                freed = original_size - final_size
                total_preview_freed += freed
                logger.info(f"  {path.name}: {comments} comments, would free {_format_bytes(freed)}")
            except Exception as e:
                logger.error(f"  {path.name}: {e}")

        if len(source_files) > 5:
            logger.info(f"  ... and {len(source_files) - 5} more files")
            logger.info(
                f"Preview: Would free approximately {_format_bytes(total_preview_freed)} (for {5} processed files)"
            )

        return 0

    # Process files
    logger.info(f"Using {num_workers or cpu_count()} workers for parallel processing")
    results = process_files_parallel(source_files, num_workers)

    # Print summary
    print_summary(results, target_paths)

    # Cleanup backups if requested
    if not keep_backups:
        logger.info("Removing backup files...")
        backup_count = 0
        for result in results:
            if result.success:
                backup_path = result.path.with_suffix(result.path.suffix + ".bak")
                if backup_path.exists():
                    backup_path.unlink()
                    backup_count += 1
        logger.info(f"Removed {backup_count} backup files")

    # Check for failures
    failed = [r for r in results if not r.success]
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Remove comments from C/C++ files recursively",
        epilog="Examples:\n"
        "  %(prog)s                           # Process current directory\n"
        "  %(prog)s src/ include/             # Process multiple directories\n"
        "  %(prog)s file.cpp                  # Process single file\n"
        "  %(prog)s src/ file.h               # Process directory and file\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("targets", nargs="*", help="Files or directories to process (default: current directory)")
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        help="Number of parallel workers (default: CPU count)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Remove .bak backup files after processing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files",
    )

    args = parser.parse_args()
    targets = args.targets if args.targets else None

    exit_code = main(
        targets=targets,
        num_workers=args.workers,
        keep_backups=not args.no_backup,
        dry_run=args.dry_run,
    )
    sys.exit(exit_code)
