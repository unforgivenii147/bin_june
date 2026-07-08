#!/data/data/com.termux/files/usr/bin/env python
"""
Recursive Python file runner with parallel processing and timeout handling.
Runs all .py files in a directory tree, continuing even if some fail.
"""

import sys
import subprocess
import traceback
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional
import argparse
import multiprocessing
import queue
import time


def run_python_file(file_path: Path, timeout: int = 10) -> Tuple[Path, bool, Optional[str], Optional[str]]:
    """
    Run a single Python file with timeout.

    Returns:
        Tuple of (file_path, success, error_type, error_message)
    """
    try:
        # Run the Python file with timeout
        result = subprocess.run(
            [sys.executable, str(file_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=file_path.parent,  # Run in the file's directory
        )

        if result.returncode == 0:
            return (file_path, True, None, None)
        else:
            # Determine error type from stderr
            stderr = result.stderr.lower()
            error_type = "Unknown Error"
            error_msg = result.stderr or result.stdout

            if "modulenotfounderror" in stderr or "no module named" in stderr:
                error_type = "ModuleNotFoundError"
            elif "syntaxerror" in stderr:
                error_type = "SyntaxError"
            elif "importerror" in stderr:
                error_type = "ImportError"
            elif "attributeerror" in stderr:
                error_type = "AttributeError"
            elif "typeerror" in stderr:
                error_type = "TypeError"
            elif "valueerror" in stderr:
                error_type = "ValueError"
            elif "keyboardinterrupt" in stderr:
                error_type = "KeyboardInterrupt"
            else:
                error_type = f"RuntimeError (exit code: {result.returncode})"

            return (file_path, False, error_type, error_msg.strip())

    except subprocess.TimeoutExpired:
        return (file_path, False, "TimeoutError", f"Execution exceeded {timeout} seconds")
    except subprocess.SubprocessError as e:
        return (file_path, False, "SubprocessError", str(e))
    except Exception as e:
        return (file_path, False, "UnexpectedError", f"{type(e).__name__}: {str(e)}")


def find_python_files(root_dir: Path, recursive: bool = True) -> List[Path]:
    """
    Find all Python files in a directory tree.
    """
    if recursive:
        return sorted(root_dir.rglob("*.py"))
    else:
        return sorted(root_dir.glob("*.py"))


def run_files_parallel(
    files: List[Path], max_workers: Optional[int] = None, timeout: int = 10, verbose: bool = False
) -> Dict[str, List[Tuple[Path, str]]]:
    """
    Run multiple Python files in parallel with a timeout.

    Returns:
        Dictionary with 'success' and 'failed' lists
    """
    if max_workers is None:
        max_workers = min(multiprocessing.cpu_count(), len(files))

    results = {"success": [], "failed": []}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(run_python_file, file_path, timeout): file_path for file_path in files}

        # Process completed tasks
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                file_path, success, error_type, error_msg = future.result()

                if success:
                    results["success"].append(file_path)
                    if verbose:
                        print(f"✅ {file_path}")
                else:
                    results["failed"].append((file_path, error_type, error_msg))
                    if verbose:
                        print(f"❌ {file_path}: {error_type}")
                        if error_msg:
                            print(f"   {error_msg}")

            except Exception as e:
                # This catches any unexpected errors in the future processing
                results["failed"].append((file_path, "FutureError", str(e)))
                if verbose:
                    print(f"❌ {file_path}: FutureError - {e}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Recursively run Python files with timeout and parallel processing")
    parser.add_argument(
        "directory",
        type=str,
        nargs="?",
        default=".",
        help="Directory to scan for Python files (default: current directory)",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", default=True, help="Recursively search subdirectories (default: True)"
    )
    parser.add_argument("-t", "--timeout", type=int, default=10, help="Timeout in seconds per file (default: 10)")
    parser.add_argument(
        "-w", "--workers", type=int, default=None, help="Number of parallel workers (default: CPU count)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed output")
    parser.add_argument("--no-recursive", action="store_false", dest="recursive", help="Don't scan subdirectories")

    args = parser.parse_args()

    # Get the directory path
    root_dir = Path(args.directory).resolve()
    if not root_dir.exists():
        print(f"Error: Directory '{root_dir}' does not exist")
        sys.exit(1)

    if not root_dir.is_dir():
        print(f"Error: '{root_dir}' is not a directory")
        sys.exit(1)

    # Find Python files
    print(f"Scanning {'recursively' if args.recursive else 'non-recursively'} in: {root_dir}")
    files = find_python_files(root_dir, args.recursive)

    if not files:
        print("No Python files found.")
        return

    print(f"Found {len(files)} Python files")
    print(f"Using {args.workers or 'auto'} workers with {args.timeout}s timeout per file")
    print("-" * 60)

    # Run files in parallel
    start_time = time.time()
    results = run_files_parallel(files=files, max_workers=args.workers, timeout=args.timeout, verbose=args.verbose)
    elapsed_time = time.time() - start_time

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total files: {len(files)}")
    print(f"✅ Successfully ran: {len(results['success'])}")
    print(f"❌ Failed: {len(results['failed'])}")
    print(f"Time elapsed: {elapsed_time:.2f} seconds")

    # Print failed files details
    if results["failed"]:
        print("\n" + "-" * 60)
        print("FAILED FILES:")
        print("-" * 60)
        for file_path, error_type, error_msg in results["failed"]:
            print(f"\n📁 {file_path}")
            print(f"   Error: {error_type}")
            if error_msg:
                # Truncate long error messages
                if len(error_msg) > 200:
                    error_msg = error_msg[:200] + "..."
                print(f"   Message: {error_msg}")

    # Exit with error code if any failed
    if results["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
