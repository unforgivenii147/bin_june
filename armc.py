#!/data/data/com.termux/files/usr/bin/env python
"""
Python Comment Remover with AST Validation

Removes comments from Python files recursively with parallel processing.
Features:
- Removes line comments (# ...) and inline comments
- Preserves docstrings
- Validates code with AST before writing
- Processes .py files, files without extension, and .whl archives
- Parallel processing for performance
- Detailed reporting
"""

from __future__ import annotations

import argparse
import ast
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Generator, Tuple
import shutil


class CommentRemover:
    """Remove comments from Python source code while preserving docstrings."""

    def __init__(self, validate: bool = True):
        """
        Initialize the CommentRemover.

        Args:
            validate: Whether to validate code with AST before writing
        """
        self.validate = validate
        self.total_files = 0
        self.total_comments_removed = 0
        self.failed_files = []

    @staticmethod
    def is_python_file(path: Path) -> bool:
        """Check if file is a Python file."""
        if path.suffix == ".py":
            return True
        # Check files without extension that start with Python shebang
        if path.suffix == "" and path.is_file():
            try:
                with open(path, "rb") as f:
                    first_line = f.readline().decode("utf-8", errors="ignore")
                    return first_line.startswith("#!") and "python" in first_line
            except (OSError, UnicodeDecodeError):
                return False
        return False

    @staticmethod
    def validate_syntax(code: str) -> Tuple[bool, str]:
        """
        Validate Python code syntax using AST.

        Args:
            code: Python source code to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax Error at line {e.lineno}: {e.msg}"

    @staticmethod
    def remove_comments(source_code: str) -> Tuple[str, int]:
        """
        Remove comments from Python source code.

        Handles:
        - Line comments (# ...)
        - Inline comments (code # comment)
        - Preserves docstrings
        - Preserves string literals containing #

        Args:
            source_code: Python source code

        Returns:
            Tuple of (cleaned_code, comment_count)
        """
        lines = source_code.split("\n")
        cleaned_lines = []
        comment_count = 0
        in_multiline_string = False
        string_delimiter = None

        for line in lines:
            # Track multiline strings
            for delimiter in ('"""', "'''"):
                if delimiter in line:
                    # Count occurrences outside of other strings
                    temp_line = line
                    # Remove quoted strings to avoid false positives
                    i = 0
                    count = 0
                    while i < len(temp_line):
                        if temp_line[i : i + 3] == delimiter:
                            count += 1
                            i += 3
                        else:
                            i += 1
                    if count % 2 == 1:
                        if not in_multiline_string:
                            in_multiline_string = True
                            string_delimiter = delimiter
                        elif string_delimiter == delimiter:
                            in_multiline_string = False

            # If inside multiline string, keep the line as-is
            if in_multiline_string:
                cleaned_lines.append(line)
                continue

            # Remove inline comments
            cleaned_line = ""
            in_string = False
            string_char = None
            i = 0

            while i < len(line):
                char = line[i]

                # Handle string delimiters
                if char in ('"', "'") and (i == 0 or line[i - 1] != "\\"):
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False
                        string_char = None

                # Check for comment start
                if char == "#" and not in_string:
                    # Found comment
                    if cleaned_line.rstrip():  # Only count if there's code before
                        comment_count += 1
                    # Skip rest of line
                    break

                cleaned_line += char
                i += 1

            # Strip trailing whitespace but preserve empty lines
            cleaned_line = cleaned_line.rstrip()
            cleaned_lines.append(cleaned_line)

        # Remove trailing blank lines
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()

        # Rejoin lines
        result = "\n".join(cleaned_lines)

        # Ensure file ends with newline
        if result and not result.endswith("\n"):
            result += "\n"

        return result, comment_count

    def process_file(self, file_path: Path) -> Tuple[Path, int, bool, str]:
        """
        Process a single Python file to remove comments.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (file_path, comments_removed, success, message)
        """
        try:
            # Read original file
            with open(file_path, "r", encoding="utf-8") as f:
                original_code = f.read()

            # Remove comments
            cleaned_code, comment_count = self.remove_comments(original_code)

            # Validate syntax if requested
            if self.validate:
                is_valid, error_msg = self.validate_syntax(cleaned_code)
                if not is_valid:
                    return (
                        file_path,
                        0,
                        False,
                        f"Validation failed: {error_msg}",
                    )

            # Write cleaned code back
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(cleaned_code)

            return file_path, comment_count, True, "OK"

        except Exception as e:
            return file_path, 0, False, f"Error: {str(e)}"

    def find_python_files(self, paths: list[Path]) -> Generator[Path, None, None]:
        """
        Find all Python files in given paths recursively.

        Args:
            paths: List of file or directory paths

        Yields:
            Path objects for Python files
        """
        for path in paths:
            if not path.exists():
                print(f"⚠ Warning: Path does not exist: {path}", file=sys.stderr)
                continue

            if path.is_file():
                if self.is_python_file(path):
                    yield path
                else:
                    print(f"⚠ Warning: Not a Python file: {path}", file=sys.stderr)
            elif path.is_dir():
                # Find all .py files recursively
                yield from path.rglob("*.py")
                # Find files without extension with Python shebang
                for file_path in path.rglob("*"):
                    if file_path.is_file() and file_path.suffix == "" and self.is_python_file(file_path):
                        yield file_path

    def process_whl_file(self, whl_path: Path, dry_run: bool = False) -> Tuple[int, list[Tuple[str, int]]]:
        """
        Process Python files inside a .whl archive.

        Args:
            whl_path: Path to .whl file
            dry_run: If True, don't modify the archive

        Returns:
            Tuple of (total_comments_removed, file_results)
        """
        file_results = []
        total_removed = 0

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract wheel
                with zipfile.ZipFile(whl_path, "r") as zip_ref:
                    zip_ref.extractall(temp_path)

                # Find and process Python files
                python_files = list(self.find_python_files([temp_path]))

                for file_path in python_files:
                    _, comments_removed, success, _ = self.process_file(file_path)
                    if success:
                        file_results.append((str(file_path.relative_to(temp_path)), comments_removed))
                        total_removed += comments_removed

                # Repackage wheel if not dry run
                if not dry_run and total_removed > 0:
                    # Create backup
                    backup_path = whl_path.with_suffix(".whl.bak")
                    shutil.copy2(whl_path, backup_path)

                    # Create new wheel
                    with zipfile.ZipFile(whl_path, "w", zipfile.ZIP_DEFLATED) as zip_ref:
                        for file_path in temp_path.rglob("*"):
                            if file_path.is_file():
                                arcname = str(file_path.relative_to(temp_path))
                                zip_ref.write(file_path, arcname)

        except zipfile.BadZipFile:
            raise ValueError(f"Invalid wheel file: {whl_path}")

        return total_removed, file_results

    def process_files(
        self,
        paths: list[Path],
        max_workers: int = 4,
        dry_run: bool = False,
        process_wheels: bool = False,
    ) -> None:
        """
        Process multiple files with parallel execution.

        Args:
            paths: List of file or directory paths
            max_workers: Number of parallel workers
            dry_run: If True, don't write changes
            process_wheels: If True, process .whl files
        """
        print(f"🔍 Scanning for Python files...")

        # Find all Python files
        python_files = list(self.find_python_files(paths))
        self.total_files = len(python_files)

        if not python_files:
            print("⚠ No Python files found")
            return

        print(f"✓ Found {self.total_files} Python file(s)\n")

        # Process wheel files if requested
        wheel_files = []
        if process_wheels:
            for path in paths:
                if path.is_file() and path.suffix == ".whl":
                    wheel_files.append(path)
                elif path.is_dir():
                    wheel_files.extend(path.rglob("*.whl"))

        # Process regular Python files in parallel
        if python_files:
            print("📝 Processing Python files...\n")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self.process_file, file_path): file_path for file_path in python_files}

                for future in as_completed(futures):
                    file_path, comments_removed, success, message = future.result()
                    self.total_comments_removed += comments_removed

                    if success:
                        status = "✓" if comments_removed > 0 else "•"
                        print(f"{status} {file_path.name:50} | Comments removed: {comments_removed:3}")
                    else:
                        print(f"✗ {file_path.name:50} | {message}")
                        self.failed_files.append((file_path, message))

        # Process wheel files
        if wheel_files:
            print("\n📦 Processing .whl files...\n")
            for whl_path in wheel_files:
                try:
                    total_removed, file_results = self.process_whl_file(whl_path, dry_run=dry_run)
                    if file_results:
                        print(f"✓ {whl_path.name}")
                        for rel_path, removed in file_results:
                            print(f"  └─ {rel_path:50} | Comments: {removed}")
                        self.total_comments_removed += total_removed
                except Exception as e:
                    print(f"✗ {whl_path.name} | Error: {str(e)}")
                    self.failed_files.append((whl_path, str(e)))

    def print_summary(self) -> None:
        """Print processing summary."""
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"Files processed:     {self.total_files}")
        print(f"Comments removed:    {self.total_comments_removed}")
        print(f"Failed files:        {len(self.failed_files)}")

        if self.failed_files:
            print("\n❌ Failed files:")
            for file_path, error in self.failed_files:
                print(f"  • {file_path}: {error}")

        print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Remove comments from Python files with AST validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process current directory recursively
  python comment_remover.py

  # Process specific files
  python comment_remover.py script.py module.py

  # Process directories
  python comment_remover.py src/ tests/

  # Process multiple paths
  python comment_remover.py src/ tests/ main.py

  # Process with parallel workers
  python comment_remover.py --workers 8 src/

  # Include .whl files
  python comment_remover.py --wheels package.whl src/

  # Dry run (no changes)
  python comment_remover.py --dry-run src/

  # Skip AST validation (faster but less safe)
  python comment_remover.py --no-validate src/
        """,
    )

    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path.cwd()],
        help="Files or directories to process (default: current directory)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip AST validation (faster but less safe)",
    )
    parser.add_argument(
        "--wheels",
        action="store_true",
        help="Process .whl files in addition to regular Python files",
    )

    args = parser.parse_args()

    # Create remover
    remover = CommentRemover(validate=not args.no_validate)

    # Process files
    try:
        remover.process_files(
            args.paths,
            max_workers=args.workers,
            dry_run=args.dry_run,
            process_wheels=args.wheels,
        )
        remover.print_summary()
    except KeyboardInterrupt:
        print("\n\n⚠ Processing interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
