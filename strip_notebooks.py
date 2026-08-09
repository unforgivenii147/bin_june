#!/data/data/com.termux/files/home/.local/bin/python
"""
Strip outputs from Jupyter notebook (.ipynb) files.

Usage:
    python strip_notebooks.py [paths...]

If no paths are provided, processes all .ipynb files recursively from current directory.
"""

import json
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Set
import argparse


def find_notebook_files(paths: List[Path]) -> Set[Path]:
    """Find all .ipynb files from given paths, recursively for directories."""
    notebook_files = set()

    for path in paths:
        if not path.exists():
            print(f"Warning: {path} does not exist, skipping.", file=sys.stderr)
            continue

        if path.is_file():
            if path.suffix == ".ipynb":
                notebook_files.add(path.resolve())
            else:
                print(f"Warning: {path} is not a .ipynb file, skipping.", file=sys.stderr)
        elif path.is_dir():
            # Recursively find all .ipynb files in directory
            for nb_file in path.rglob("*.ipynb"):
                # Skip checkpoints and hidden directories
                if ".ipynb_checkpoints" not in str(nb_file):
                    notebook_files.add(nb_file.resolve())

    return notebook_files


def strip_notebook_output(notebook_path: Path) -> tuple:
    """
    Strip outputs from a single notebook file.
    Returns (path, success, message).
    """
    try:
        # Read the notebook
        with open(notebook_path, "r", encoding="utf-8") as f:
            notebook = json.load(f)

        # Check if it's a valid notebook
        if "cells" not in notebook:
            return (notebook_path, False, "Not a valid notebook (no 'cells' key)")

        modified = False

        # Process each cell
        for cell in notebook["cells"]:
            if cell.get("cell_type") == "code":
                # Clear outputs
                if "outputs" in cell and cell["outputs"]:
                    cell["outputs"] = []
                    modified = True

                # Clear execution count
                if "execution_count" in cell and cell["execution_count"] is not None:
                    cell["execution_count"] = None
                    modified = True

        # Clear notebook-level metadata about execution
        if "metadata" in notebook:
            if "kernelspec" in notebook["metadata"]:
                # Keep kernel info but clear execution-specific metadata
                pass

        # Write back only if modified
        if modified:
            with open(notebook_path, "w", encoding="utf-8") as f:
                json.dump(notebook, f, indent=1, ensure_ascii=False)
                f.write("\n")  # Add trailing newline
            return (notebook_path, True, "Outputs stripped")
        else:
            return (notebook_path, True, "No outputs to strip")

    except json.JSONDecodeError as e:
        return (notebook_path, False, f"Invalid JSON: {e}")
    except Exception as e:
        return (notebook_path, False, f"Error: {e}")


def process_notebooks(paths: List[Path], max_workers: int = None):
    """Process multiple notebooks in parallel."""
    # Find all notebook files
    notebook_files = find_notebook_files(paths)

    if not notebook_files:
        print("No .ipynb files found to process.")
        return

    print(f"Found {len(notebook_files)} notebook(s) to process...")

    # Process in parallel
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_path = {executor.submit(strip_notebook_output, path): path for path in notebook_files}

        # Collect results as they complete
        for future in as_completed(future_to_path):
            path, success, message = future.result()
            results.append((path, success, message))

            # Print progress
            status = "✓" if success else "✗"
            relative_path = path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
            print(f"{status} {relative_path}: {message}")

    # Summary
    successful = sum(1 for _, success, _ in results if success)
    failed = len(results) - successful

    if failed > 0:
        print(f"\nProcessed: {successful} succeeded, {failed} failed")
    else:
        print(f"\nSuccessfully processed {successful} notebook(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Strip outputs from Jupyter notebook (.ipynb) files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Process all .ipynb files in current directory recursively
  %(prog)s notebook.ipynb     # Process a single file
  %(prog)s dir1/ dir2/        # Process all .ipynb files in dir1 and dir2 recursively
  %(prog)s *.ipynb            # Process multiple notebook files
  %(prog)s -w 4 .             # Use 4 worker processes
        """,
    )

    parser.add_argument(
        "paths", nargs="*", default=["."], help="Files or directories to process (default: current directory)"
    )

    parser.add_argument(
        "-w", "--workers", type=int, default=None, help="Number of worker processes (default: CPU count)"
    )

    args = parser.parse_args()

    # Convert paths to Path objects
    paths = [Path(p) for p in args.paths]

    try:
        process_notebooks(paths, max_workers=args.workers)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
