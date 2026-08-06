#!/data/data/com.termux/files/home/.local/bin/python
"""Reverse inline functions by extracting them back to dh package imports."""

import argparse
import ast
import hashlib
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def get_function_source_hash(source: str, func_name: str) -> str | None:
    """Get SHA-256 hash of a function's source code."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            # Extract the function source text
            lines = source.split("\n")
            func_lines = lines[node.lineno - 1 : node.end_lineno]
            func_source = "\n".join(func_lines)
            # Create a hash of the function source
            return hashlib.sha256(func_source.encode()).hexdigest()
    return None


def extract_functions_from_module(module_path: Path) -> dict[str, tuple[str, str]]:
    """Extract functions from a module with their source hashes.
    Returns dict mapping function_name -> (module_name, source_hash)
    """
    if not module_path.is_file():
        return {}
    try:
        with open(module_path, "r", encoding="utf-8") as f:
            source = f.read()
            tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return {}
    functions = {}
    module_name = module_path.stem
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Get hash of the function source
            func_hash = get_function_source_hash(source, node.name)
            if func_hash:
                functions[node.name] = (module_name, func_hash)
    return functions


def build_dh_function_map(dh_src_path: Path) -> dict[str, tuple[str, str]]:
    """Build a map of dh functions with their source hashes.
    Returns dict mapping function_name -> (module_name, source_hash)
    """
    func_map = {}
    for module_file in dh_src_path.glob("*.py"):
        if module_file.name == "__init__.py":
            continue
        functions = extract_functions_from_module(module_file)
        func_map.update(functions)
    return func_map


def find_matching_inlined_functions(source: str, dh_func_map: dict[str, tuple[str, str]]) -> list[tuple[str, int, int]]:
    """Find inlined functions that match dh functions by source hash.
    Returns list of (function_name, start_line, end_line)
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in dh_func_map:
            # Check if the function source hash matches
            func_hash = get_function_source_hash(source, node.name)
            dh_module_name, dh_hash = dh_func_map[node.name]
            if func_hash and func_hash == dh_hash:
                matches.append((node.name, node.lineno - 1, node.end_lineno))
    return matches


def has_import(source: str, func_name: str) -> bool:
    """Check if the function is already imported from dh package."""
    return (
        f"from dh.{func_name} import" in source
        or f"from dh import {func_name}" in source
        or f"from dh import" in source
        and f"{func_name}" in source
    )


def add_imports(lines: list[str], imports: set[tuple[str, str]]) -> list[str]:
    """Add import statements for dh functions."""
    if not imports:
        return lines
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.startswith(("import ", "from ")):
            last_import_idx = i
    import_lines = sorted([f"from dh.{module} import {func}" for func, module in imports])
    if last_import_idx == -1:
        return import_lines + [""] + lines
    else:
        return lines[: last_import_idx + 1] + import_lines + lines[last_import_idx + 1 :]


def process_file(
    file_path: Path, dh_func_map: dict[str, tuple[str, str]], dry_run: bool = True
) -> tuple[Path, int, set[tuple[str, str]]]:
    """Process a single Python file to replace inlined functions with imports.
    Returns (file_path, number_of_imports_added, set_of_imports)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, UnicodeDecodeError):
        return (file_path, 0, set())
    matches = find_matching_inlined_functions(content, dh_func_map)
    if not matches:
        return (file_path, 0, set())
    lines = content.split("\n")
    imports_needed = set()
    for func_name, start_line, end_line in matches:
        if not has_import(content, func_name):
            module_name, _ = dh_func_map[func_name]
            imports_needed.add((func_name, module_name))
    if not imports_needed:
        return (file_path, 0, set())
    if not dry_run:
        matches_sorted = sorted(matches, key=lambda x: x[1], reverse=True)
        for func_name, start_line, end_line in matches_sorted:
            del lines[start_line:end_line]
        lines = add_imports(lines, imports_needed)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    return (file_path, len(imports_needed), imports_needed)


def main():
    parser = argparse.ArgumentParser(description="Reverse inline functions from dh package")
    parser.add_argument("-n", "--no-dry-run", action="store_true", help="Actually modify files (dry-run by default)")
    parser.add_argument("paths", nargs="*", help="Files or directories to process")
    args = parser.parse_args()
    dry_run = not args.no_dry_run
    dh_path = Path.home() / "isaac" / "pkgs" / "dh" / "src" / "dh"
    bin_path = Path.cwd()
    target_paths = [Path(p).expanduser() for p in args.paths] if args.paths else [bin_path]
    if not dh_path.is_dir():
        print(f"Error: dh package not found at {dh_path}")
        sys.exit(1)
    print(f"Building function map from {dh_path}...")
    dh_func_map = build_dh_function_map(dh_path)
    print(f"Found {len(dh_func_map)} functions in dh package\n")
    py_files = []
    for target_path in target_paths:
        if target_path.is_file() and target_path.suffix == ".py":
            py_files.append(target_path)
        elif target_path.is_dir():
            py_files.extend(target_path.rglob("*.py"))
    mode = "DRY RUN" if dry_run else "ACTUAL"
    print(f"{mode} MODE: Processing {len(py_files)} Python files...\n")
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(process_file, py_file, dh_func_map, dry_run): py_file for py_file in py_files}
        total_removed = 0
        changes_by_file = {}
        for future in as_completed(futures):
            file_path, count, imports = future.result()
            if count > 0:
                changes_by_file[file_path] = imports
                total_removed += count
    if not changes_by_file:
        print("No matching inlined dh functions found (identical by content hash).")
        return
    for file_path in sorted(changes_by_file.keys()):
        imports = changes_by_file[file_path]
        print(f"{file_path.name}:")
        for func_name, module_name in sorted(imports):
            print(f"  - Replace {func_name}() and add: from dh.{module_name} import {func_name}")
        print()
    print(f"Total functions to process: {total_removed}")
    if dry_run:
        print("\n✓ DRY RUN complete. Run with -n/--no-dry-run to apply changes.")
    else:
        print("\n✓ Changes applied successfully.")


if __name__ == "__main__":
    main()
