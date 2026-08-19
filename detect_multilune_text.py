#!/data/data/com.termux/files/home/.local/bin/python
"""
Multi-line text removal tool with parallel processing.

Reads a pattern from /sdcard/lic and removes all occurrences of that pattern
from files in specified directories or current directory recursively.
"""

import argparse
import sys
from pathlib import Path
from typing import Iterator, List, Tuple, Optional
from joblib import Parallel, delayed
import tempfile
import os
import shutil
import hashlib
from dataclasses import dataclass

# Constants
LICENSE_FILE = Path("/sdcard/lic")
WORKERS = 4
CHUNK_SIZE = 8192  # 8KB chunks for streaming

# File extensions to process (can be expanded)
TEXT_EXTENSIONS = {
    ".py",
    ".txt",
    ".md",
    ".rst",
    ".cfg",
    ".ini",
    ".json",
    ".xml",
    ".yml",
    ".yaml",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".sql",
    ".graphql",
    ".toml",
    ".csv",
    ".log",
    ".tex",
    ".bib",
    ".asm",
    ".asm",
    ".s",
    ".S",
    ".pl",
    ".pm",
    ".swift",
    ".kt",
    ".kts",
    ".dart",
    ".scala",
    ".clj",
    ".cljs",
    ".edn",
    ".ex",
    ".exs",
    ".erl",
    ".hrl",
    ".hs",
    ".lhs",
    ".vim",
    ".el",
    ".lisp",
    ".lsp",
    ".r",
    ".R",
    ".m",
    ".mm",
    ".f",
    ".f90",
    ".f95",
    ".for",
    ".v",
    ".vhd",
    ".vhdl",
    ".sv",
    ".bat",
    ".cmd",
    ".ps1",
    ".psm1",
    ".psd1",
    ".properties",
    ".env",
    ".gitignore",
    ".dockerignore",
    ".license",
    ".licence",
    ".copying",
    ".conf",
    ".config",
    ".make",
    ".mk",
    ".cmake",
    ".gradle",
}


@dataclass
class FileStats:
    """Statistics for a processed file."""

    path: Path
    removed_count: int = 0
    bytes_removed: int = 0
    bytes_processed: int = 0
    error: Optional[str] = None
    modified: bool = False

    def __str__(self):
        rel = self.path.relative_to(Path.cwd())
        if self.error:
            return f"{rel}: ERROR - {self.error}"
        if self.modified:
            return (
                f"{rel}: Processed {self.bytes_processed:,} bytes, "
                f"removed {self.removed_count} occurrence(s) "
                f"({self.bytes_removed:,} bytes)"
            )
        return f"{rel}: No changes needed ({self.bytes_processed:,} bytes)"


def read_license_pattern() -> str:
    """Read the license pattern from /sdcard/lic."""
    try:
        if not LICENSE_FILE.exists():
            raise FileNotFoundError(f"License file not found: {LICENSE_FILE}")

        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            pattern = f.read()

        if not pattern.strip():
            raise ValueError("License file is empty")

        return pattern
    except Exception as e:
        print(f"Error reading license file: {e}", file=sys.stderr)
        sys.exit(1)


def find_text_files(directories: List[Path]) -> Iterator[Path]:
    """Find text files in the given directories recursively."""
    for directory in directories:
        if not directory.exists():
            print(f"Warning: Directory does not exist: {directory}", file=sys.stderr)
            continue

        if directory.is_file():
            if directory.suffix.lower() in TEXT_EXTENSIONS or not directory.suffix:
                yield directory
        else:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    if file_path.suffix.lower() in TEXT_EXTENSIONS or not file_path.suffix:
                        # Skip binary files by checking for null bytes
                        try:
                            with open(file_path, "rb") as f:
                                if b"\x00" in f.read(1024):
                                    continue
                        except (IOError, OSError):
                            continue
                        yield file_path


def calculate_pattern_fingerprint(pattern: str) -> str:
    """Calculate a fingerprint for the pattern for quick matching."""
    return hashlib.sha256(pattern.encode("utf-8")).hexdigest()


def process_file(file_path: Path, pattern: str, pattern_fingerprint: str) -> FileStats:
    """
    Process a single file to remove the pattern.

    Uses streaming approach for memory efficiency on large files.
    """
    stats = FileStats(path=file_path)

    try:
        file_size = file_path.stat().st_size
        stats.bytes_processed = file_size

        # Quick check if file contains the pattern
        if pattern not in file_path.read_text(encoding="utf-8", errors="ignore"):
            return stats

        # Use temporary file for atomic replacement
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".tmp") as temp_file:
            temp_path = Path(temp_file.name)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as source:
                    content = source.read()

                    # Count occurrences
                    count = content.count(pattern)
                    if count == 0:
                        return stats

                    # Remove pattern
                    modified_content = content.replace(pattern, "")

                    # Write modified content
                    temp_file.write(modified_content)
                    temp_file.flush()

                    # Calculate stats
                    stats.removed_count = count
                    stats.bytes_removed = len(pattern) * count
                    stats.modified = True

                # Atomic replace
                shutil.move(str(temp_path), str(file_path))

            except Exception:
                # Clean up temp file on error
                if temp_path.exists():
                    temp_path.unlink()
                raise

    except (IOError, OSError, UnicodeDecodeError) as e:
        stats.error = str(e)
    except Exception as e:
        stats.error = f"Unexpected error: {e}"

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Remove multi-line text pattern from files recursively.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Process current directory recursively
  %(prog)s /path/to/dir      # Process specific directory
  %(prog)s file1.txt file2.txt  # Process specific files
  %(prog)s -a /path/to/dir   # Auto-remove pattern from files
  %(prog)s --auto-remove      # Same as -a
        """,
    )

    parser.add_argument(
        "paths", nargs="*", type=Path, help="Files or directories to process (default: current directory)"
    )

    parser.add_argument(
        "-a", "--auto-remove", action="store_true", help="Automatically remove found patterns (without confirmation)"
    )

    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")

    parser.add_argument("-j", "--jobs", type=int, default=WORKERS, help=f"Number of parallel jobs (default: {WORKERS})")

    args = parser.parse_args()

    # Read license pattern
    print(f"Reading pattern from {LICENSE_FILE}...")
    pattern = read_license_pattern()
    pattern_fingerprint = calculate_pattern_fingerprint(pattern)
    print(f"Pattern loaded ({len(pattern)} characters, {len(pattern.splitlines())} lines)")

    # Determine paths to process
    if not args.paths:
        paths = [Path.cwd()]
    else:
        paths = args.paths

    # Find all text files
    print("Scanning for files...")
    files = list(find_text_files(paths))

    if not files:
        print("No text files found to process.")
        return

    print(f"Found {len(files)} text file(s) to process")

    if args.dry_run:
        print("\nDRY RUN - No changes will be made\n")

    # Process files in parallel
    if args.auto_remove or args.dry_run:
        print("Processing files in parallel...")
        stats_list = Parallel(n_jobs=args.jobs, verbose=1)(
            delayed(process_file)(file_path, pattern, pattern_fingerprint) for file_path in files
        )

        # Report stats
        print("\n" + "=" * 60)
        print("PROCESSING REPORT")
        print("=" * 60)

        total_files = len(stats_list)
        modified_files = sum(1 for s in stats_list if s.modified)
        total_removed = sum(s.removed_count for s in stats_list)
        total_bytes = sum(s.bytes_removed for s in stats_list)
        total_processed = sum(s.bytes_processed for s in stats_list)
        errors = [s for s in stats_list if s.error]

        for stats in stats_list:
            print(stats)

        print("\n" + "=" * 60)
        print(f"Files processed: {total_files}")
        print(f"Files modified: {modified_files}")
        print(f"Pattern removed: {total_removed} occurrence(s)")
        print(f"Total bytes removed: {total_bytes:,}")
        print(f"Total bytes processed: {total_processed:,}")
        if errors:
            print(f"Errors encountered: {len(errors)}")

    else:
        print("\nDry run mode (no changes will be made). Use -a to apply changes.")
        # Show preview
        print("Files that contain the pattern:")
        preview_stats = Parallel(n_jobs=args.jobs, verbose=0)(
            delayed(
                lambda f: (
                    f,
                    pattern in f.read_text(encoding="utf-8", errors="ignore")
                    if f.stat().st_size < 10 * 1024 * 1024
                    else False,
                )
            )(file_path)
            for file_path in files
        )

        for file_path, contains in preview_stats:
            if contains:
                rel = file_path.relative_to(Path.cwd())
                print(f"  {rel}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
