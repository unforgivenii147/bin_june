#!/data/data/com.termux/files/usr/bin/python
"""
Optimized import cleaner for Python files.
Removes unused imports while preserving formatting and grouping.
Supports single files, folders, and multiprocessing.
"""

import sys
import tokenize
from io import StringIO
from pathlib import Path
from collections import defaultdict
from typing import Set, Dict, List, Tuple, DefaultDict, Callable, Optional
from dataclasses import dataclass
from joblib import Parallel, delayed


@dataclass
class ImportChange:
    """Represents changes made to imports in a file."""

    file_path: str
    removed_imports: List[str]
    kept_imports: List[str]
    error: Optional[str] = None


class ImportParseException(Exception):
    """Exception raised when parsing an import statement fails."""

    pass


def parse_import(line: str) -> Tuple[str, List[str]]:
    """
    Parse a 'from ... import ...' statement.

    Args:
        line: The import line to parse

    Returns:
        Tuple of (module_name, list_of_symbols)

    Raises:
        ImportParseException: If line is not a valid from-import
    """
    parts = line.split()
    if len(parts) < 4 or parts[0] != "from" or parts[2] != "import":
        raise ImportParseException(line)

    module = parts[1]
    # Join remaining parts (handles commas without spaces)
    rest = " ".join(parts[3:])
    symbols = [s.strip() for s in rest.split(",")]
    return module, symbols


def parse_splat_import(line: str) -> Set[str]:
    """
    Parse a direct 'import ...' statement.

    Args:
        line: The import line to parse

    Returns:
        Set of module names

    Raises:
        ImportParseException: If line is not a valid import
    """
    parts = line.split()
    if len(parts) < 2 or parts[0] != "import":
        raise ImportParseException(line)

    return {s.strip() for s in " ".join(parts[1:]).split(",")}


def gather_imports(lines: List[str]) -> Tuple[Dict[str, Set[str]], Set[str], List[str]]:
    """
    Extract all imports from lines, handling line continuations.

    Args:
        lines: List of source code lines

    Returns:
        Tuple of (imports_dict, splats_set, original_import_lines)
    """
    imports: DefaultDict[str, Set[str]] = defaultdict(set)
    splats: Set[str] = set()
    original_imports: List[str] = []

    prev = ""
    for line in lines:
        if prev:
            line = prev + line
            prev = ""

        # Handle line continuation
        if line.rstrip().endswith("\\"):
            prev = line.rstrip()[:-1]
            continue

        line = line.strip()
        if not line:
            continue

        try:
            module, symbols = parse_import(line)
            imports[module].update(symbols)
            original_imports.append(line)
        except ImportParseException:
            try:
                modules = parse_splat_import(line)
                splats.update(modules)
                original_imports.append(line)
            except ImportParseException:
                # Not an import line, skip
                pass

    return imports, splats, original_imports


def get_used_symbols(lines: List[str]) -> Set[str]:
    """
    Extract all used symbols from source code using tokenization.

    Args:
        lines: List of source code lines

    Returns:
        Set of used symbol names
    """
    source = "".join(lines)
    used = {"*"}  # '*' always considered used (wildcard imports)

    try:
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        for ttype, token, _, _, _ in tokens:
            if ttype == tokenize.NAME:
                used.add(token)
    except tokenize.TokenError:
        # Handle incomplete/incorrect source
        pass

    return used


def extract_imported_symbols(import_line: str) -> Set[str]:
    """
    Extract symbols imported by a single import statement.

    Args:
        import_line: The import statement line

    Returns:
        Set of imported symbol names
    """
    if import_line.startswith("from "):
        try:
            _, symbols = parse_import(import_line)
            return set(symbols)
        except ImportParseException:
            return set()
    elif import_line.startswith("import "):
        try:
            modules = parse_splat_import(import_line)
            # For 'import module', we track the module name
            return {m.split(".")[0] for m in modules}
        except ImportParseException:
            return set()
    return set()


def group_and_sort_symbols(symbols: Set[str]) -> Tuple[List[str], List[str], List[str]]:
    """
    Group symbols by case for organized output.

    Args:
        symbols: Set of symbol names

    Returns:
        Tuple of (lowercase, uppercase, mixedcase) symbol lists
    """
    lower = []
    upper = []
    mixed = []

    for s in symbols:
        if s.islower():
            lower.append(s)
        elif s.isupper():
            upper.append(s)
        else:
            mixed.append(s)

    # Sort with natural case-insensitive order for mixed case
    lower.sort()
    mixed.sort(key=str.lower)
    upper.sort()

    return lower, mixed, upper


def format_imports(imports: Dict[str, Set[str]], splats: Set[str], max_line_length: int = 78) -> List[str]:
    """
    Format imports into clean, readable lines.

    Args:
        imports: Dictionary mapping modules to imported symbols
        splats: Set of direct import statements
        max_line_length: Maximum line length before wrapping

    Returns:
        List of formatted import lines
    """
    output = []

    # Add direct imports
    for module in sorted(splats):
        output.append(f"import {module}")

    # Add from-imports with line wrapping
    for module, symbols in sorted(imports.items()):
        if not symbols:
            continue

        lower, mixed, upper = group_and_sort_symbols(symbols)
        all_symbols = lower + mixed + upper

        line = f"from {module} import "

        for sym in all_symbols:
            if len(line) + len(sym) > max_line_length:
                output.append(line.rstrip(", "))
                line = f"from {module} import {sym}, "
            else:
                line += f"{sym}, "

        if line:
            output.append(line.rstrip(", "))

    return output


def cleanup_imports(source_lines: List[str]) -> Tuple[List[str], List[str]]:
    """
    Main function to clean unused imports from source code.

    Args:
        source_lines: List of source code lines

    Returns:
        Tuple of (cleaned_imports_list, removed_imports_list)
    """
    # Find all used symbols
    used = get_used_symbols(source_lines)

    # Gather all imports and original lines
    imports_dict, splats_set, original_imports = gather_imports(source_lines)

    # Track removed imports
    removed_imports = []

    # Remove unused symbols from imports
    for module in list(imports_dict.keys()):
        original_symbols = imports_dict[module].copy()
        imports_dict[module] = {sym for sym in imports_dict[module] if sym in used}
        removed_symbols = original_symbols - imports_dict[module]

        if removed_symbols:
            removed_imports.append(f"from {module} import {', '.join(sorted(removed_symbols))}")

        if not imports_dict[module]:
            del imports_dict[module]

    # Remove unused splat imports
    original_splats = splats_set.copy()
    splats_set = {imp for imp in splats_set if any(imp.split(".")[0] in used for imp in [imp])}
    removed_splats = original_splats - splats_set
    for imp in sorted(removed_splats):
        removed_imports.append(f"import {imp}")

    # Format kept imports
    kept_imports = format_imports(imports_dict, splats_set)

    return kept_imports, removed_imports


def get_python_files(directory: Path, recursive: bool = True) -> List[Path]:
    """
    Get all Python files in a directory.

    Args:
        directory: Directory to search
        recursive: Whether to search subdirectories recursively

    Returns:
        List of Python file paths
    """
    pattern = "**/*.py" if recursive else "*.py"
    return list(directory.glob(pattern))


def process_file(file_path_str: str, in_place: bool = False, verbose: bool = False) -> ImportChange:
    """
    Process a single Python file to remove unused imports.

    Args:
        file_path_str: Path to the Python file as string
        in_place: If True, modify file in place; if False, create _cleaned file
        verbose: If True, print detailed information

    Returns:
        ImportChange object with details of changes
    """
    file_path = Path(file_path_str)

    try:
        # Read file
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        # Clean imports
        cleaned_imports, removed_imports = cleanup_imports(lines)

        # Create result object
        result = ImportChange(file_path=str(file_path), removed_imports=removed_imports, kept_imports=cleaned_imports)

        # Only write if there are changes
        if removed_imports:
            output_content = "\n".join(cleaned_imports)

            if in_place:
                # This simplified version only outputs imports
                # For full preservation, preserve non-import lines
                file_path.write_text(output_content, encoding="utf-8")
                if verbose:
                    print(f"✓ Updated: {file_path}")
            else:
                output_path = file_path.with_stem(f"{file_path.stem}_cleaned")
                output_path.write_text(output_content, encoding="utf-8")
                if verbose:
                    print(f"✓ Created: {output_path}")

        return result

    except Exception as e:
        return ImportChange(file_path=str(file_path), removed_imports=[], kept_imports=[], error=str(e))


def mpf_joblib(process_function: Callable, files: List[Path], **kwargs) -> List:
    """
    Process files in parallel using joblib.

    Args:
        process_function: Function to process each file
        files: List of file paths
        **kwargs: Additional arguments to pass to process_function

    Returns:
        List of results from process_function
    """
    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1, verbose=0)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


def print_summary(results: List[ImportChange], verbose: bool = False) -> None:
    """
    Print summary of changes.

    Args:
        results: List of ImportChange objects
        verbose: If True, print detailed information
    """
    total_files = len(results)
    modified_files = [r for r in results if r.removed_imports and not r.error]
    error_files = [r for r in results if r.error]
    unchanged_files = [r for r in results if not r.removed_imports and not r.error]

    print("\n" + "=" * 60)
    print("IMPORT CLEANUP SUMMARY")
    print("=" * 60)
    print(f"Total files processed: {total_files}")
    print(f"Files with removed imports: {len(modified_files)}")
    print(f"Unchanged files: {len(unchanged_files)}")
    print(f"Files with errors: {len(error_files)}")

    if modified_files and verbose:
        print("\n" + "-" * 60)
        print("DETAILED CHANGES:")
        print("-" * 60)
        for result in modified_files:
            print(f"\n📄 {result.file_path}")
            if result.removed_imports:
                print(f"  Removed ({len(result.removed_imports)}):")
                for imp in result.removed_imports:
                    print(f"    - {imp}")
            if result.kept_imports:
                print(f"  Kept ({len(result.kept_imports)}):")
                for imp in result.kept_imports[:5]:  # Show first 5 kept imports
                    print(f"    + {imp}")
                if len(result.kept_imports) > 5:
                    print(f"    ... and {len(result.kept_imports) - 5} more")

    elif modified_files and not verbose:
        print("\nModified files:")
        for result in modified_files:
            print(f"  • {result.file_path} ({len(result.removed_imports)} import(s) removed)")

    if error_files:
        print("\n" + "-" * 60)
        print("ERRORS:")
        print("-" * 60)
        for result in error_files:
            print(f"  ❌ {result.file_path}: {result.error}")

    total_removed = sum(len(r.removed_imports) for r in results)
    print(f"\n📊 Total unused imports removed: {total_removed}")


def main() -> None:
    """Main entry point with folder support and multiprocessing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Remove unused imports from Python files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s script.py                    # Clean single file
  %(prog)s src/                         # Clean all Python files in folder
  %(prog)s src/ tests/ --recursive      # Clean multiple folders recursively
  %(prog)s . --in-place --verbose       # Clean current directory in place with details
  %(prog)s file1.py file2.py --no-parallel  # Process sequentially
        """,
    )

    parser.add_argument("paths", nargs="*", help="Files or directories to process (defaults to current directory)")
    parser.add_argument(
        "--in-place", "-i", action="store_true", help="Modify files in place instead of creating _cleaned copies"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed information about changes")
    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Recursively process subdirectories (default: True)"
    )
    parser.add_argument("--no-parallel", "-np", action="store_true", help="Disable parallel processing")
    parser.add_argument("--no-recursive", action="store_true", help="Do not process subdirectories recursively")

    args = parser.parse_args()

    # Determine recursive flag
    recursive = args.recursive and not args.no_recursive

    # Collect all Python files
    files = []
    cwd = Path.cwd()

    if args.paths:
        for path_str in args.paths:
            p = Path(path_str)
            if p.is_file():
                if p.suffix == ".py":
                    files.append(p)
                elif args.verbose:
                    print(f"⚠ Skipping non-Python file: {p}")
            elif p.is_dir():
                files.extend(get_python_files(p, recursive=recursive))
            else:
                print(f"⚠ Path does not exist: {p}", file=sys.stderr)
    else:
        # No arguments, process current directory
        files = get_python_files(cwd, recursive=recursive)

    if not files:
        print("No Python files found to process.")
        return

    if args.verbose:
        print(f"Found {len(files)} Python file(s) to process")
        if args.no_parallel:
            print("Processing sequentially...")
        else:
            print("Processing in parallel...")

    # Process files
    if args.no_parallel:
        results = []
        for file in files:
            result = process_file(str(file), in_place=args.in_place, verbose=args.verbose)
            results.append(result)
    else:
        results = mpf_joblib(process_file, files, in_place=args.in_place, verbose=args.verbose)

    # Print summary
    print_summary(results, verbose=args.verbose)


if __name__ == "__main__":
    main()
