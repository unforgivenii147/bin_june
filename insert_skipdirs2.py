#!/data/data/com.termux/files/usr/bin/env python
"""
Insert SKIP_DIRS definition after import section in Python files that use it but don't define it.
Uses parallel processing for better performance.
Handles edge cases like try-except blocks and validates output.
"""

import ast
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Tuple

SKIP_DIRS_DEF = (
    'SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})\n'
)

IGNORE_DIRS = frozenset({
    "lazy",
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
})


def check_skip_dirs_usage(tree: ast.AST) -> bool:
    """
    Check if SKIP_DIRS is used anywhere in the AST (name reference).
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "SKIP_DIRS":
            return True
    return False


def check_skip_dirs_defined(tree: ast.AST) -> bool:
    """
    Check if SKIP_DIRS is defined at module level.
    """
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SKIP_DIRS":
                    return True
    return False


def get_module_level_imports(tree: ast.AST) -> int:
    """
    Find the line number after the last module-level import.
    Ignores imports inside functions, classes, or try-except blocks.
    Returns the end line number of the last import statement.
    """
    last_import_line = 0

    for node in tree.body:
        # Only process top-level statements (depth == 1 in tree.body)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if node.end_lineno and node.end_lineno > last_import_line:
                last_import_line = node.end_lineno
        # Stop at first non-import, non-docstring statement
        elif not isinstance(node, ast.Expr):  # Skip docstrings
            break

    return last_import_line


def find_insert_position(content: str) -> Optional[int]:
    """
    Find the position after the last module-level import statement.
    Uses AST for precise parsing to ignore imports in try-except blocks.
    """
    try:
        tree = ast.parse(content)
        last_import_line = get_module_level_imports(tree)

        if last_import_line > 0:
            # Convert line number to string position
            lines = content.splitlines(True)
            # Handle case where file has fewer lines than expected
            if last_import_line <= len(lines):
                pos = sum(len(line) for line in lines[:last_import_line])
                return pos
    except SyntaxError:
        pass

    return None


def find_fallback_insert_position(content: str) -> int:
    """
    Fallback: find position after shebang, encoding, and docstring.
    """
    lines = content.splitlines(True)
    start_pos = 0
    line_idx = 0

    # Skip shebang
    if lines and lines[0].startswith("#!"):
        start_pos += len(lines[0])
        line_idx += 1

    # Skip encoding declaration
    if line_idx < len(lines) and "coding" in lines[line_idx]:
        start_pos += len(lines[line_idx])
        line_idx += 1

    # Skip module docstring if present
    remaining_content = content[start_pos:]
    remaining_stripped = remaining_content.lstrip()

    # Check for docstring
    for quote in ('"""', "'''"):
        if remaining_stripped.startswith(quote):
            # Find end of docstring
            idx = remaining_stripped.find(quote, len(quote))
            if idx != -1:
                # Add offset to account for whitespace
                offset = len(remaining_content) - len(remaining_stripped)
                start_pos += offset + idx + len(quote)
                break

    return start_pos


def validate_modified_code(original: str, modified: str) -> bool:
    """
    Validate that modified code is still valid Python.
    """
    try:
        ast.parse(modified)
        return True
    except SyntaxError as e:
        return False


def process_file(file_path: Path) -> Tuple[Path, bool, str]:
    """
    Process a single Python file.
    Returns (file_path, was_modified, status_message).
    """
    try:
        # Read file content
        content = file_path.read_text(encoding="utf-8")

        # Parse the file
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return file_path, False, f"syntax_error_original"

        # Check if SKIP_DIRS is used
        if not check_skip_dirs_usage(tree):
            return file_path, False, "no_skip_dirs_usage"

        # Check if SKIP_DIRS is already defined
        if check_skip_dirs_defined(tree):
            return file_path, False, "already_defined"

        # Find insert position
        insert_pos = find_insert_position(content)

        if insert_pos is None:
            # Fallback to after shebang, encoding, docstring
            insert_pos = find_fallback_insert_position(content)

        # Ensure proper newline separation
        if insert_pos > 0:
            before_char = content[insert_pos - 1 : insert_pos]
            if before_char not in ("\n", "\r"):
                insert_text = "\n" + SKIP_DIRS_DEF
            else:
                insert_text = SKIP_DIRS_DEF
        else:
            insert_text = SKIP_DIRS_DEF

        # Create modified content
        modified_content = content[:insert_pos] + insert_text + content[insert_pos:]

        # Validate modified code before writing
        if not validate_modified_code(content, modified_content):
            return file_path, False, "validation_failed"

        # Write back to file
        file_path.write_text(modified_content, encoding="utf-8")

        return file_path, True, "success"

    except Exception as e:
        return file_path, False, f"exception: {str(e)}"


def find_python_files(root_dir: Path = Path(".")) -> list[Path]:
    """Find all Python files, respecting IGNORE_DIRS."""
    python_files = []

    for py_file in root_dir.rglob("*.py"):
        # Check if any parent directory should be ignored
        parts = set(py_file.parent.parts)
        if parts & IGNORE_DIRS:
            continue
        python_files.append(py_file)

    return sorted(python_files)


def main():
    """Main function to process all Python files."""
    root_dir = Path(".")

    # Find all Python files
    print("Finding Python files that use SKIP_DIRS...")
    python_files = find_python_files(root_dir)
    print(f"Found {len(python_files)} Python files\n")

    if not python_files:
        print("No Python files to process")
        return

    # Track statistics
    stats = {
        "modified": 0,
        "already_defined": 0,
        "no_usage": 0,
        "validation_failed": 0,
        "syntax_error": 0,
        "other_errors": 0,
    }

    print(f"Processing files using {min(len(python_files), 8)} workers...\n")

    with ProcessPoolExecutor(max_workers=min(len(python_files), 8)) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_file, file_path): file_path for file_path in python_files}

        # Process results as they complete
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                path, was_modified, status = future.result()

                if was_modified:
                    stats["modified"] += 1
                    print(f"✓ Modified: {path}")
                elif status == "already_defined":
                    stats["already_defined"] += 1
                elif status == "no_skip_dirs_usage":
                    stats["no_usage"] += 1
                elif status == "validation_failed":
                    stats["validation_failed"] += 1
                    print(f"✗ Validation failed: {path}")
                elif status == "syntax_error_original":
                    stats["syntax_error"] += 1
                    print(f"✗ Syntax error: {path}")
                else:
                    stats["other_errors"] += 1
                    print(f"✗ {status}: {path}")

            except Exception as e:
                stats["other_errors"] += 1
                print(f"✗ Exception processing {file_path}: {e}")

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Total files found:           {len(python_files)}")
    print(f"  Modified (uses but not defined): {stats['modified']}")
    print(f"  Already defined:             {stats['already_defined']}")
    print(f"  No SKIP_DIRS usage:          {stats['no_usage']}")
    print(f"  Validation failed:           {stats['validation_failed']}")
    print(f"  Syntax errors:               {stats['syntax_error']}")
    print(f"  Other errors:                {stats['other_errors']}")
    print(f"{'=' * 60}")

    if stats["modified"] > 0:
        print(f"\n✓ Successfully added SKIP_DIRS definition to {stats['modified']} file(s)")
    else:
        print(f"\nℹ No files needed SKIP_DIRS definition")


if __name__ == "__main__":
    main()
