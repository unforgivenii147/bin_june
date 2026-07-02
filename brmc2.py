#!/data/data/com.termux/files/usr/bin/env python
"""
Remove docstrings from Python files while preserving module docstrings.

This script recursively processes Python files and removes docstrings from
functions, classes, and methods while keeping module-level docstrings intact.
It uses parallel processing for performance and validates output with ast.parse.

Optimized for Python 3.12+ on Linux.
"""

import ast
import sys
from pathlib import Path
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DocstringRemover(ast.NodeTransformer):
    """AST transformer that removes docstrings while preserving module docstrings."""

    def __init__(self):
        self.is_module = True
        self.preserve_module_docstring = True

    def visit_Module(self, node: ast.Module) -> ast.Module:
        """Visit module node and preserve its docstring."""
        self.is_module = True

        # Keep module docstring if present
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            # First statement is the module docstring, keep it
            module_docstring = node.body[0]
            remaining_body = self.generic_visit_body(node.body[1:])
            node.body = [module_docstring] + remaining_body
        else:
            # No module docstring, process normally
            node.body = self.generic_visit_body(node.body)

        self.is_module = False
        return node

    def generic_visit_body(self, body: list) -> list:
        """Process body statements and remove docstrings."""
        new_body = []

        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                new_body.append(self.visit(node))
            else:
                new_body.append(self.visit(node))

        return new_body

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Visit function definition and remove its docstring."""
        return self._process_function_like(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        """Visit async function definition and remove its docstring."""
        return self._process_function_like(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Visit class definition and remove its docstring."""
        new_body = self._remove_docstring_from_body(node.body)
        node.body = new_body
        node.decorator_list = [self.visit(dec) for dec in node.decorator_list]
        return node

    def _process_function_like(self, node):
        """Process function-like nodes (FunctionDef or AsyncFunctionDef)."""
        new_body = self._remove_docstring_from_body(node.body)
        node.body = new_body
        node.decorator_list = [self.visit(dec) for dec in node.decorator_list]
        return node

    def _remove_docstring_from_body(self, body: list) -> list:
        """Remove docstring from body and add pass if needed."""
        if not body:
            return body

        new_body = []

        # Check if first statement is a docstring
        if (
            isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            # Skip the docstring
            body = body[1:]

        # Process remaining body
        for node in body:
            new_body.append(self.visit(node))

        # If body is now empty, add a pass statement
        if not new_body:
            new_body = [ast.Pass()]

        return new_body


def remove_docstrings_from_code(source_code: str) -> Optional[str]:
    """
    Remove docstrings from Python source code.

    Args:
        source_code: Python source code as string

    Returns:
        Modified source code with docstrings removed, or None if processing fails
    """
    try:
        # Parse the source code
        tree = ast.parse(source_code)

        # Apply transformation
        transformer = DocstringRemover()
        new_tree = transformer.visit(tree)

        # Validate the transformed tree
        ast.fix_missing_locations(new_tree)

        # Verify it's valid Python
        compile(new_tree, "<transformed>", "exec")

        # Unparse back to source code
        return ast.unparse(new_tree)

    except SyntaxError as e:
        logger.error(f"Syntax error in transformed code: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing code: {e}")
        return None


def validate_python_code(code: str) -> bool:
    """
    Validate Python code using ast.parse.

    Args:
        code: Python source code to validate

    Returns:
        True if code is valid, False otherwise
    """
    try:
        ast.parse(code)
        compile(code, "<string>", "exec")
        return True
    except (SyntaxError, ValueError) as e:
        logger.error(f"Code validation failed: {e}")
        return False


def process_file(file_path: Path) -> tuple[Path, bool, Optional[str]]:
    """
    Process a single Python file to remove docstrings.

    Args:
        file_path: Path to the Python file

    Returns:
        Tuple of (file_path, success, error_message)
    """
    try:
        # Read original file
        original_code = file_path.read_text(encoding="utf-8")

        # Validate original code
        if not validate_python_code(original_code):
            return file_path, False, "Original code validation failed"

        # Remove docstrings
        modified_code = remove_docstrings_from_code(original_code)

        if modified_code is None:
            return file_path, False, "Docstring removal failed"

        # Validate modified code
        if not validate_python_code(modified_code):
            return file_path, False, "Modified code validation failed"

        # Write back to file
        file_path.write_text(modified_code, encoding="utf-8")

        return file_path, True, None

    except Exception as e:
        return file_path, False, str(e)


def find_python_files(paths: list[Path]) -> list[Path]:
    """
    Recursively find all Python files in given paths.

    Args:
        paths: List of file or directory paths

    Returns:
        List of Python file paths
    """
    python_files = []

    for path in paths:
        if path.is_file() and path.suffix == ".py":
            python_files.append(path)
        elif path.is_dir():
            # Recursively find .py files
            python_files.extend(path.rglob("*.py"))

    return sorted(set(python_files))  # Remove duplicates and sort


def main():
    """Main entry point."""
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_paths = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Default to current directory
        input_paths = [Path.cwd()]

    # Validate paths exist
    for path in input_paths:
        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            sys.exit(1)

    # Find all Python files
    python_files = find_python_files(input_paths)

    if not python_files:
        logger.warning("No Python files found to process")
        sys.exit(0)

    logger.info(f"Found {len(python_files)} Python file(s) to process")

    # Determine optimal worker count for Linux/Python 3.12+
    # Use CPU count but cap at reasonable value for I/O bound work
    max_workers = min(os.cpu_count() or 1, len(python_files), 32)

    # Process files in parallel
    successful = 0
    failed = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_file, file_path): file_path for file_path in python_files}

        # Process completed tasks as they finish
        for future in as_completed(future_to_file):
            file_path, success, error = future.result()

            if success:
                logger.info(f"✓ Processed: {file_path}")
                successful += 1
            else:
                logger.error(f"✗ Failed: {file_path} - {error}")
                failed += 1

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Processing complete:")
    logger.info(f"  Successful: {successful}")
    logger.info(f"  Failed:     {failed}")
    logger.info(f"  Total:      {len(python_files)}")
    logger.info(f"{'=' * 60}")

    # Exit with error code if any files failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
