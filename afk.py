#!/usr/bin/env python3
"""
Remove unused imports from Python files using pyflakes.

Features:
  - Processes a single file or recursively scans a directory.
  - Defaults to the current directory if no path is given.
  - Uses multiprocessing for speedup.
  - Globally ignores ``__init__.py`` files.
  - Handles edge cases like star imports (left untouched) and imports inside
    conditionals (replaced with `pass` where needed).
  - Reports the names of removed imports for every modified file.

Requirements:
  - Python 3.9+ (for `ast.unparse`)
  - pyflakes (``pip install pyflakes``)

Note: The AST-based rewriting does **not** preserve comments or original
formatting; it regenerates the code with canonical layout.
"""

import argparse
import ast
import multiprocessing
import pathlib
import sys
from typing import Dict, List, Set, Tuple

import pyflakes.api
import pyflakes.messages
import pyflakes.reporter


class UnusedImportCollector(pyflakes.reporter.Reporter):
    """A pyflakes reporter that only collects UnusedImport messages."""

    def __init__(self):
        super().__init__()
        self.unused: List[pyflakes.messages.UnusedImport] = []

    def unexpectedError(self, filename, msg):
        pass

    def syntaxError(self, filename, msg, lineno, offset, text):
        pass

    def flake(self, msg):
        if isinstance(msg, pyflakes.messages.UnusedImport):
            self.unused.append(msg)


def get_unused_imports(file_path: pathlib.Path) -> List[pyflakes.messages.UnusedImport]:
    """Run pyflakes on *file_path* and return the list of UnusedImport messages."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return []
    reporter = UnusedImportCollector()
    try:
        pyflakes.api.check(source, str(file_path), reporter=reporter)
    except Exception as e:
        print(f"Error checking {file_path}: {e}", file=sys.stderr)
        return []
    return reporter.unused


def process_file(file_path: pathlib.Path) -> Tuple[str, List[str]]:
    """
    Detect and remove unused imports in *file_path*.
    Returns (string path, list of removed import names).
    """
    unused_msgs = get_unused_imports(file_path)
    if not unused_msgs:
        return (str(file_path), [])

    source = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return (str(file_path), [])

    # Map line number -> set of unused names reported on that line
    line_unused: Dict[int, Set[str]] = {}
    for msg in unused_msgs:
        line_unused.setdefault(msg.lineno, set()).add(msg.name)

    removed_names: List[str] = []

    class ImportTransformer(ast.NodeTransformer):
        def visit_Import(self, node):
            if node.lineno in line_unused:
                unused_set = line_unused[node.lineno]
                new_aliases = []
                for alias in node.names:
                    bound_name = alias.asname if alias.asname else alias.name
                    if bound_name in unused_set:
                        removed_names.append(bound_name)
                    else:
                        new_aliases.append(alias)
                if not new_aliases:
                    # All aliases removed → replace the whole statement with `pass`
                    return ast.Pass()
                node.names = new_aliases
            return node

        def visit_ImportFrom(self, node):
            if node.lineno in line_unused:
                unused_set = line_unused[node.lineno]
                new_names = []
                for alias in node.names:
                    # Star imports (`from x import *`) have alias.name == '*'
                    if alias.name == "*":
                        new_names.append(alias)
                        continue
                    bound_name = alias.asname if alias.asname else alias.name
                    if bound_name in unused_set:
                        removed_names.append(bound_name)
                    else:
                        new_names.append(alias)
                if not new_names:
                    return ast.Pass()
                node.names = new_names
            return node

    transformer = ImportTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)

    new_source = ast.unparse(new_tree)
    file_path.write_text(new_source, encoding="utf-8")
    return (str(file_path), removed_names)


def find_py_files(root: pathlib.Path) -> List[pathlib.Path]:
    """Find all .py files under *root*, skipping `__init__.py`."""
    if root.is_file():
        if root.suffix == ".py" and root.name != "__init__.py":
            return [root]
        return []
    # Recursive glob
    return [p for p in root.rglob("*.py") if p.name != "__init__.py"]


def main():
    parser = argparse.ArgumentParser(description="Remove unused imports from Python files.")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="File or directory to process (default: current directory)",
    )
    args = parser.parse_args()

    input_path = pathlib.Path(args.path).resolve()
    py_files = find_py_files(input_path)

    if not py_files:
        print("No Python files found.")
        return

    with multiprocessing.Pool() as pool:
        results = pool.map(process_file, py_files)

    # Report removed imports per file
    for file_path, removed in results:
        if removed:
            print(f"{file_path}: removed {', '.join(removed)}")


if __name__ == "__main__":
    main()
