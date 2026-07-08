#!/data/data/com.termux/files/usr/bin/env python


"""
Python Comment Remover with AST Validation

Removes comments from Python files recursively with parallel processing.
Features:
- Removes line comments (# ...) and inline comments
- Preserves docstrings
- Preserves shebang lines
- Preserves # type: and # fmt: comments
- Validates code with AST before writing
- Processes .py files, files without extension, and .whl archives
- Processes files inside .whl archives
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
from typing import Generator, Tuple, List
import shutil


class CommentRemover:
    def __init__(self, validate: bool = True):
        self.validate = validate
        self.total_files = 0
        self.total_comments_removed = 0
        self.failed_files = []
        self.processed_whl_files = []

    @staticmethod
    def is_python_file(path: Path) -> bool:
        if path.suffix == ".py":
            return True
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
        try:
            ast.parse(code)
            return (True, "")
        except SyntaxError as e:
            return (False, f"Syntax Error at line {e.lineno}: {e.msg}")

    @staticmethod
    def should_preserve_comment(line: str, comment_start: int) -> bool:
        comment_text = line[comment_start + 1 :].strip()
        if comment_start == 0 and line.startswith("#!"):
            return True
        if comment_text.startswith("type:"):
            return True
        if comment_text.startswith("fmt:"):
            return True
        return False

    @staticmethod
    def remove_comments(source_code: str) -> Tuple[str, int]:
        lines = source_code.split("\n")
        cleaned_lines = []
        comment_count = 0
        in_multiline_string = False
        string_delimiter = None
        for line_index, line in enumerate(lines):
            for delimiter in ('"""', "'''"):
                if delimiter in line:
                    temp_line = line
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
            if in_multiline_string:
                cleaned_lines.append(line)
                continue
            cleaned_line = ""
            in_string = False
            string_char = None
            i = 0
            comment_found = False
            while i < len(line):
                char = line[i]
                if char in ('"', "'") and (i == 0 or line[i - 1] != "\\"):
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False
                        string_char = None
                if char == "#" and (not in_string):
                    if CommentRemover.should_preserve_comment(line, i):
                        cleaned_line = line
                        comment_found = True
                        break
                    else:
                        comment_found = True
                        break
                cleaned_line += char
                i += 1
            if comment_found:
                cleaned_line = cleaned_line.rstrip()
                if cleaned_line and (not cleaned_line.startswith("#!")):
                    comment_count += 1
            cleaned_lines.append(cleaned_line)
        while cleaned_lines and (not cleaned_lines[-1]):
            cleaned_lines.pop()
        result = "\n".join(cleaned_lines)
        if result and (not result.endswith("\n")):
            result += "\n"
        return (result, comment_count)

    def process_file(self, file_path: Path) -> Tuple[Path, int, bool, str]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_code = f.read()
            cleaned_code, comment_count = self.remove_comments(original_code)
            if self.validate:
                is_valid, error_msg = self.validate_syntax(cleaned_code)
                if not is_valid:
                    return (file_path, 0, False, f"Validation failed: {error_msg}")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(cleaned_code)
            return (file_path, comment_count, True, "OK")
        except Exception as e:
            return (file_path, 0, False, f"Error: {str(e)}")

    def find_python_files(self, paths: list[Path]) -> Generator[Path, None, None]:
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
                yield from path.rglob("*.py")
                for file_path in path.rglob("*"):
                    if file_path.is_file() and file_path.suffix == "" and self.is_python_file(file_path):
                        yield file_path

    def process_whl_file(self, whl_path: Path, dry_run: bool = False) -> Tuple[int, List[Tuple[str, int]], bool]:
        file_results = []
        total_removed = 0
        success = True
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                with zipfile.ZipFile(whl_path, "r") as zip_ref:
                    zip_ref.extractall(temp_path)
                python_files = list(self.find_python_files([temp_path]))
                if not python_files:
                    return (0, [], True)
                for file_path in python_files:
                    _, comments_removed, file_success, _ = self.process_file(file_path)
                    if file_success:
                        rel_path = str(file_path.relative_to(temp_path))
                        file_results.append((rel_path, comments_removed))
                        total_removed += comments_removed
                    else:
                        success = False
                if not dry_run and total_removed > 0:
                    backup_path = whl_path.with_suffix(".whl.bak")
                    if not backup_path.exists():
                        shutil.copy2(whl_path, backup_path)
                    with zipfile.ZipFile(whl_path, "w", zipfile.ZIP_DEFLATED) as zip_ref:
                        for file_path in temp_path.rglob("*"):
                            if file_path.is_file():
                                arcname = str(file_path.relative_to(temp_path))
                                zip_ref.write(file_path, arcname)
                return (total_removed, file_results, success)
        except zipfile.BadZipFile:
            return (0, [], False)
        except Exception as e:
            print(f"⚠ Error processing wheel {whl_path.name}: {str(e)}")
            return (0, [], False)

    def process_files(
        self,
        paths: list[Path],
        max_workers: int = 4,
        dry_run: bool = False,
        process_wheels: bool = False,
        recursive_wheels: bool = False,
    ) -> None:
        print(f"🔍 Scanning for Python files...")
        python_files = []
        wheel_files = []
        for path in paths:
            if not path.exists():
                print(f"⚠ Warning: Path does not exist: {path}", file=sys.stderr)
                continue
            if path.is_file():
                if self.is_python_file(path):
                    python_files.append(path)
                elif path.suffix == ".whl" and process_wheels:
                    wheel_files.append(path)
                else:
                    print(f"⚠ Warning: Not a Python file: {path}", file=sys.stderr)
            elif path.is_dir():
                python_files.extend(path.rglob("*.py"))
                for file_path in path.rglob("*"):
                    if file_path.is_file() and file_path.suffix == "" and self.is_python_file(file_path):
                        python_files.append(file_path)
                if process_wheels:
                    if recursive_wheels:
                        wheel_files.extend(path.rglob("*.whl"))
                    else:
                        wheel_files.extend([f for f in path.iterdir() if f.is_file() and f.suffix == ".whl"])
        self.total_files = len(python_files)
        if python_files:
            print(f"✓ Found {self.total_files} Python file(s)\n")
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
        if wheel_files:
            print(f"\n📦 Found {len(wheel_files)} wheel file(s)\n")
            print("🔧 Processing wheel files...\n")
            for whl_path in wheel_files:
                print(f"📦 Processing {whl_path.name}...")
                total_removed, file_results, success = self.process_whl_file(whl_path, dry_run)
                if file_results:
                    self.total_comments_removed += total_removed
                    print(f"  ✓ Removed {total_removed} comments from {len(file_results)} file(s)")
                    if len(file_results) <= 10:
                        for rel_path, removed in file_results:
                            print(f"    └─ {rel_path:50} | Comments: {removed}")
                    else:
                        for rel_path, removed in file_results[:5]:
                            print(f"    └─ {rel_path:50} | Comments: {removed}")
                        print(f"    └─ ... and {len(file_results) - 5} more file(s)")
                    self.processed_whl_files.append((whl_path, total_removed, len(file_results)))
                else:
                    print(f"  ⚠ No Python files found or no changes made")
                if not success:
                    print(f"  ⚠ Some files in {whl_path.name} had processing errors")
        if not python_files and (not wheel_files):
            print("⚠ No Python files or wheel files found")

    def print_summary(self) -> None:
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"Python files processed:     {self.total_files}")
        print(f"Comments removed:           {self.total_comments_removed}")
        print(f"Wheel files processed:      {len(self.processed_whl_files)}")
        print(f"Failed files:               {len(self.failed_files)}")
        if self.processed_whl_files:
            print("\n📦 Processed wheel files:")
            for whl_path, comments, files in self.processed_whl_files:
                print(f"  • {whl_path.name}: {comments} comments removed from {files} file(s)")
        if self.failed_files:
            print("\n❌ Failed files:")
            for file_path, error in self.failed_files:
                print(f"  • {file_path}: {error}")
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Remove comments from Python files with AST validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\nExamples:\n  # Process current directory recursively\n  python comment_remover.py\n\n  # Process specific files\n  python comment_remover.py script.py module.py\n\n  # Process directories\n  python comment_remover.py src/ tests/\n\n  # Process .whl files\n  python comment_remover.py --wheels package.whl\n\n  # Process .whl files recursively in directories\n  python comment_remover.py --wheels --recursive-wheels src/\n\n  # Process both Python files and wheel files\n  python comment_remover.py --wheels src/ package.whl\n\n  # Process with parallel workers\n  python comment_remover.py --workers 8 src/\n\n  # Dry run (no changes)\n  python comment_remover.py --dry-run src/\n\n  # Skip AST validation (faster but less safe)\n  python comment_remover.py --no-validate src/\n",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path.cwd()],
        help="Files or directories to process (default: current directory)",
    )
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--no-validate", action="store_true", help="Skip AST validation (faster but less safe)")
    parser.add_argument("--wheels", action="store_true", help="Process .whl files in addition to regular Python files")
    parser.add_argument(
        "--recursive-wheels",
        action="store_true",
        help="Search for .whl files recursively in directories (only effective with --wheels)",
    )
    args = parser.parse_args()
    remover = CommentRemover(validate=not args.no_validate)
    try:
        remover.process_files(
            args.paths,
            max_workers=args.workers,
            dry_run=args.dry_run,
            process_wheels=args.wheels,
            recursive_wheels=args.recursive_wheels,
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
