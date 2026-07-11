#!/data/data/com.termux/files/usr/bin/env python
"""
Script to remove dependencies on the 'dh' custom module by inlining function code.
Supports multiple files/folders as input with parallel processing.
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
from dataclasses import dataclass
import traceback

# Configuration
DH_SOURCE_PATH = Path.home() / "isaac" / "pkgs" / "dh" / "src" / "dh"
DH_MODULE_NAME = "dh"


@dataclass
class ProcessResult:
    """Result of processing a single file."""

    file_path: Path
    modified: bool
    new_content: Optional[str]
    error: Optional[str]


class DHModuleAnalyzer:
    """Analyzes and extracts function/class definitions from dh module."""

    def __init__(self, dh_path: Path):
        self.dh_path = dh_path
        self.definitions: Dict[str, str] = {}  # function_name -> source_code
        self.module_mapping: Dict[str, Set[str]] = {}  # module -> {functions}
        self._load_dh_definitions()

    def _load_dh_definitions(self):
        """Load all function and class definitions from dh modules."""
        if not self.dh_path.exists():
            raise FileNotFoundError(f"DH module path not found: {self.dh_path}")

        py_files = sorted(self.dh_path.glob("*.py"))

        for py_file in py_files:
            if py_file.name == "__init__.py":
                continue

            module_name = py_file.stem
            self.module_mapping[module_name] = set()

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content)
                lines = content.split("\n")

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        func_name = node.name
                        start_line = node.lineno - 1
                        end_line = node.end_lineno

                        # Extract source code
                        func_source = "\n".join(lines[start_line:end_line])

                        self.definitions[func_name] = func_source
                        self.module_mapping[module_name].add(func_name)

            except Exception as e:
                print(f"⚠ Warning: Could not parse {py_file}: {e}", file=sys.stderr)

    def get_definition(self, func_name: str) -> Optional[str]:
        """Get source code for a function/class."""
        return self.definitions.get(func_name)

    def get_all_definitions(self) -> Dict[str, str]:
        """Get all definitions."""
        return self.definitions.copy()


class ImportRemover(ast.NodeTransformer):
    """AST transformer to remove 'dh' imports and track them."""

    def __init__(self, definitions: Dict[str, str]):
        self.definitions = definitions
        self.imported_names: Dict[str, str] = {}  # imported_name -> definition_source
        self.inlined_code: List[str] = []
        self.has_dh_imports = False

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Optional[ast.stmt]:
        """Handle 'from dh import ...' statements."""
        if node.module and (node.module == DH_MODULE_NAME or node.module.startswith(f"{DH_MODULE_NAME}.")):
            for alias in node.names:
                name = alias.name
                if name in self.definitions:
                    self.imported_names[alias.asname or name] = name
                    self.inlined_code.append(self.definitions[name])

            self.has_dh_imports = True
            return None  # Remove the import

        return node

    def visit_Import(self, node: ast.Import) -> Optional[ast.stmt]:
        """Handle 'import dh' statements."""
        if any(alias.name == DH_MODULE_NAME or alias.name.startswith(f"{DH_MODULE_NAME}.") for alias in node.names):
            self.has_dh_imports = True
            return None  # Remove the import

        return node


class PythonFileProcessor:
    """Processes individual Python files to remove dh dependencies."""

    def __init__(self, definitions: Dict[str, str]):
        self.definitions = definitions

    def process(self, file_path: Path) -> ProcessResult:
        """
        Process a single Python file.
        Returns ProcessResult with modification details.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()

            # Parse and transform
            tree = ast.parse(original_content)
            transformer = ImportRemover(self.definitions)
            transformer.visit(tree)

            # If no dh imports, return unchanged
            if not transformer.has_dh_imports:
                return ProcessResult(file_path=file_path, modified=False, new_content=None, error=None)

            # Build new content with inlined code
            new_content = self._build_new_content(original_content, transformer.inlined_code)

            return ProcessResult(file_path=file_path, modified=True, new_content=new_content, error=None)

        except SyntaxError as e:
            return ProcessResult(file_path=file_path, modified=False, new_content=None, error=f"Syntax error: {e}")
        except Exception as e:
            return ProcessResult(
                file_path=file_path, modified=False, new_content=None, error=f"{type(e).__name__}: {e}"
            )

    def _build_new_content(self, original_content: str, inlined_code: List[str]) -> str:
        """Build new file content with inlined code."""
        lines = original_content.split("\n")

        # Find the end of imports
        import_end_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue

            # Check if it's an import line
            if stripped.startswith(("import ", "from ")):
                import_end_idx = i + 1
            else:
                # First non-import, non-comment line
                break

        # Remove dh import lines
        filtered_lines = [line for line in lines if not ("from dh import" in line or "import dh" in line)]

        # Rebuild: imports + inlined code + rest
        new_lines = filtered_lines[:import_end_idx]

        if inlined_code:
            new_lines.append("\n# ===== Inlined from dh module =====\n")
            new_lines.extend(inlined_code)
            new_lines.append("\n# ===== End of inlined code =====\n")

        new_lines.extend(filtered_lines[import_end_idx:])

        return "\n".join(new_lines)


class ProjectCleaner:
    """Main orchestrator for cleaning the project with parallel processing."""

    def __init__(self, dh_path: Path = DH_SOURCE_PATH, max_workers: Optional[int] = None):
        self.dh_path = dh_path.resolve()
        self.max_workers = max_workers
        self.analyzer = DHModuleAnalyzer(self.dh_path)
        self.processor = PythonFileProcessor(self.analyzer.get_all_definitions())
        self.results: List[ProcessResult] = []

    def find_python_files(self, paths: List[Path]) -> List[Path]:
        """
        Find all Python files from given paths.
        Handles both files and directories.
        """
        py_files = set()

        for path in paths:
            path = path.resolve()

            if not path.exists():
                print(f"⚠ Warning: Path does not exist: {path}", file=sys.stderr)
                continue

            if path.is_file():
                if path.suffix == ".py":
                    py_files.add(path)
                else:
                    print(f"⚠ Warning: Not a Python file: {path}", file=sys.stderr)

            elif path.is_dir():
                # Recursively find .py files, skip hidden directories
                for py_file in path.rglob("*.py"):
                    if not any(part.startswith(".") for part in py_file.parts):
                        py_files.add(py_file)

        return sorted(list(py_files))

    def process_parallel(self, py_files: List[Path], dry_run: bool = False) -> Dict[str, int]:
        """
        Process files in parallel.
        Returns statistics dict.
        """
        if not py_files:
            print("No Python files to process.")
            return {"total": 0, "modified": 0, "errors": 0}

        print(f"Found {len(py_files)} Python file(s)")
        print(f"Loaded {len(self.analyzer.definitions)} definitions from dh module")
        print(f"Using {self.max_workers or 'all available'} worker(s)\n")

        modified_count = 0
        error_count = 0

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.processor.process, py_file): py_file for py_file in py_files}

            for future in as_completed(futures):
                py_file = futures[future]

                try:
                    result = future.result()
                    self.results.append(result)

                    if result.error:
                        print(f"✗ Error in {py_file}: {result.error}")
                        error_count += 1
                    elif result.modified:
                        if not dry_run:
                            with open(py_file, "w", encoding="utf-8") as f:
                                f.write(result.new_content)
                            print(f"✓ Updated: {py_file}")
                        else:
                            print(f"◇ Would update: {py_file}")
                        modified_count += 1
                    else:
                        print(f"- No changes: {py_file}")

                except Exception as e:
                    print(f"✗ Exception processing {py_file}: {e}")
                    error_count += 1

        stats = {"total": len(py_files), "modified": modified_count, "errors": error_count}

        return stats

    def print_summary(self, stats: Dict[str, int], dry_run: bool = False):
        """Print processing summary."""
        print(f"\n{'=' * 70}")
        print(f"Processing Complete!")
        print(f"{'=' * 70}")
        print(f"Total files processed:  {stats['total']}")
        print(f"Files modified:         {stats['modified']}")
        print(f"Errors:                 {stats['errors']}")

        if dry_run:
            print(f"\nⓘ Dry run mode - no changes saved")

        modified_files = [r.file_path for r in self.results if r.modified]
        if modified_files and stats["total"] <= 20:
            print(f"\nModified files:")
            for f in modified_files:
                print(f"  {f}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Remove dependencies on 'dh' module by inlining function code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process current directory recursively
  %(prog)s
  
  # Process specific files
  %(prog)s script1.py script2.py
  
  # Process specific directories
  %(prog)s src/ tests/
  
  # Mix files and directories
  %(prog)s main.py src/ tests/utils.py
  
  # Dry run to preview changes
  %(prog)s --dry-run
  
  # Custom dh module path
  %(prog)s --dh-path /path/to/dh/src/dh src/
  
  # Parallel processing with specific workers
  %(prog)s --workers 4 src/ tests/
        """,
    )

    parser.add_argument(
        "paths", nargs="*", type=Path, help="Files or directories to process (default: current directory)"
    )

    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")

    parser.add_argument(
        "--dh-path", type=Path, default=DH_SOURCE_PATH, help=f"Path to dh module source (default: {DH_SOURCE_PATH})"
    )

    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: CPU count)")

    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    return parser.parse_args()


def main():
    args = parse_args()

    # Determine paths to process
    if args.paths:
        paths = args.paths
    else:
        paths = [Path(".")]

    try:
        cleaner = ProjectCleaner(dh_path=args.dh_path, max_workers=args.workers)

        py_files = cleaner.find_python_files(paths)

        if not py_files:
            print("No Python files found to process.")
            sys.exit(0)

        stats = cleaner.process_parallel(py_files, dry_run=args.dry_run)
        cleaner.print_summary(stats, dry_run=args.dry_run)

        # Exit with error code if there were errors
        sys.exit(1 if stats["errors"] > 0 else 0)

    except FileNotFoundError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
