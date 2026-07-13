#!/data/data/com.termux/files/usr/bin/env python
"""
Remove a specific function implementation from Python files using parallel processing.
Matches the exact function structure using AST comparison.
Excludes the script itself and fileutils.py files.
"""

import sys
import time
import argparse
import textwrap
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional, Union
import ast

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
}

# The exact function source to match and remove
TARGET_FUNCTION_SOURCE = textwrap.dedent("""
def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)
""").strip()


def normalize_ast(node: ast.AST) -> str:
    """Convert AST node to normalized string for comparison."""
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def get_target_function_ast() -> ast.FunctionDef:
    """Parse the target function source and return its AST."""
    # Wrap in a module to parse
    wrapper = f"dummy_var = 1\n{TARGET_FUNCTION_SOURCE}"
    tree = ast.parse(wrapper)

    # Find the function definition in the module body
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_files":
            return node

    raise ValueError("Could not parse target function")


def functions_match(target_ast: ast.FunctionDef, candidate_ast: ast.FunctionDef) -> bool:
    """Compare two function ASTs to see if they match structurally."""

    def clean_node(node: ast.AST) -> ast.AST:
        """Create a copy of node without position information and docstring."""
        if isinstance(node, ast.FunctionDef):
            # Remove docstring if present
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Str, ast.Constant)):
                body = body[1:]

            # Create a clean copy
            cleaned = ast.FunctionDef(
                name=node.name, args=node.args, body=body, decorator_list=[], returns=node.returns, type_comment=None
            )
            return cleaned
        return node

    # Clean both ASTs
    target_cleaned = clean_node(target_ast)
    candidate_cleaned = clean_node(candidate_ast)

    # Compare normalized versions
    target_str = normalize_ast(target_cleaned)
    candidate_str = normalize_ast(candidate_cleaned)

    return target_str == candidate_str


def find_python_files(path: Path, include_hidden: bool = False, script_path: Path = None) -> list[Path]:
    """Find all Python files in the given directory recursively."""
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    files = []
    try:
        for entry in path.rglob("*.py"):
            if entry.is_symlink():
                continue
            if not include_hidden and any(part.startswith(".") for part in entry.parts):
                continue
            if any(skip_dir in entry.parts for skip_dir in SKIP_DIRS):
                continue
            # Exclude the running script itself
            if script_path and entry.resolve() == script_path.resolve():
                continue
            # Exclude fileutils.py
            if entry.name == "fileutils.py":
                continue
            files.append(entry)
    except (PermissionError, OSError):
        pass

    return sorted(files)


def remove_matching_function(file_path: Path) -> tuple[bool, int, int]:
    """
    Remove the specific get_files function if it matches the target implementation.
    Returns (removed, original_size, new_size)
    """
    try:
        original_size = file_path.stat().st_size

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Parse the source
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False, original_size, original_size

        # Get target function AST for comparison
        target_func = get_target_function_ast()

        # Find and remove matching functions
        removed = False
        new_body = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "get_files":
                if functions_match(target_func, node):
                    removed = True
                    continue  # Skip this function (remove it)
            new_body.append(node)

        if not removed:
            return False, original_size, original_size

        # Update the tree
        tree.body = new_body
        ast.fix_missing_locations(tree)

        # Convert back to source
        new_source = ast.unparse(tree)

        # Clean up any excessive blank lines
        import re

        new_source = re.sub(r"\n{3,}", "\n\n", new_source)

        # Write back
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_source)

        new_size = file_path.stat().st_size
        return True, original_size, new_size

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False, 0, 0


def process_file(file_path: Path) -> tuple[Path, float, Optional[tuple[int, int, float]]]:
    """Process a single file and return timing and size information."""
    start_time = time.time()

    removed, original_size, new_size = remove_matching_function(file_path)

    elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds

    if removed:
        ratio = (new_size / original_size * 100) if original_size > 0 else 100
        return file_path, elapsed_time, (original_size, new_size, ratio)
    else:
        return file_path, elapsed_time, None


def format_size(size: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def main():
    parser = argparse.ArgumentParser(description="Remove specific get_files function implementation from Python files")
    parser.add_argument("paths", nargs="*", help="Files or directories to process (default: current directory)")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes (default: CPU count)")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden files and directories")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be removed without actually modifying files"
    )

    args = parser.parse_args()

    # Get the path of this script
    script_path = Path(__file__).resolve()

    # Determine paths to process
    if not args.paths:
        args.paths = ["."]

    # Validate target function
    try:
        target_func = get_target_function_ast()
        print(f"Target function parsed successfully")
        print(f"Excluding script: {script_path.name}")
        print(f"Excluding: fileutils.py")
    except Exception as e:
        print(f"Error parsing target function: {e}", file=sys.stderr)
        sys.exit(1)

    # Collect all Python files
    python_files = set()
    for path_str in args.paths:
        path = Path(path_str).resolve()
        if not path.exists():
            print(f"Warning: Path does not exist: {path}", file=sys.stderr)
            continue

        if path.is_file() and path.suffix == ".py":
            # Check if this file should be excluded
            if path.resolve() == script_path.resolve():
                print(f"Skipping script itself: {path.name}")
                continue
            if path.name == "fileutils.py":
                print(f"Skipping fileutils.py: {path}")
                continue
            python_files.add(path)
        elif path.is_dir():
            python_files.update(find_python_files(path, args.include_hidden, script_path))

    if not python_files:
        print("No Python files found to process.")
        return

    print(f"Found {len(python_files)} Python files to process")
    if args.dry_run:
        print("DRY RUN - no files will be modified")
    print()

    if args.dry_run:
        # Process sequentially for dry run to avoid issues
        for file_path in sorted(python_files):
            _, elapsed_time, sizes = process_file(file_path)
            if sizes:
                original_size, new_size, ratio = sizes
                display_path = file_path.relative_to(Path.cwd()) if file_path.is_relative_to(Path.cwd()) else file_path
                print(
                    f"{display_path} "
                    f"({elapsed_time:.2f}ms) "
                    f"{format_size(original_size)} - {format_size(new_size)} "
                    f"(ratio: {ratio:.1f}%)"
                )
    else:
        # Process files in parallel
        total_original_size = 0
        total_new_size = 0
        files_modified = 0

        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_file = {executor.submit(process_file, file_path): file_path for file_path in python_files}

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result_file, elapsed_time, sizes = future.result()

                    if sizes:
                        original_size, new_size, ratio = sizes
                        total_original_size += original_size
                        total_new_size += new_size
                        files_modified += 1

                        display_path = (
                            result_file.relative_to(Path.cwd())
                            if result_file.is_relative_to(Path.cwd())
                            else result_file
                        )
                        print(
                            f"{display_path} "
                            f"({elapsed_time:.2f}ms) "
                            f"{format_size(original_size)} - {format_size(new_size)} "
                            f"(ratio: {ratio:.1f}%)"
                        )
                    else:
                        display_path = (
                            result_file.relative_to(Path.cwd())
                            if result_file.is_relative_to(Path.cwd())
                            else result_file
                        )
                        print(f"{display_path} ({elapsed_time:.2f}ms) - No match")

                except Exception as e:
                    print(f"Error processing {file_path}: {e}", file=sys.stderr)

        # Print summary
        print()
        print(f"Summary:")
        print(f"  Files processed: {len(python_files)}")
        print(f"  Files modified: {files_modified}")
        if files_modified > 0:
            total_ratio = (total_new_size / total_original_size * 100) if total_original_size > 0 else 100
            print(
                f"  Total size change: {format_size(total_original_size)} -> {format_size(total_new_size)} ({total_ratio:.1f}%)"
            )


if __name__ == "__main__":
    main()
