#!/data/data/com.termux/files/usr/bin/python
import ast
import sys
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from multiprocessing import Pool, cpu_count
import os

from dh import cprint, get_pyfiles, mpf3


def process_file(args: tuple) -> None:
    """Process a single Python file, moving it to error dir if parsing fails."""
    path, counter, total, dry_run = args
    path = Path(path)
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}[{counter}/{total}] {path.name}")

    try:
        content = path.read_text(encoding="utf-8")
        ast.parse(content)
        if dry_run:
            print(f"  ✅ {path.name} - Valid Python syntax")
        return
    except (SyntaxError, ValueError, UnicodeDecodeError, OSError) as e:
        error_dir = path.parent / "error"
        new_path = error_dir / path.name

        if dry_run:
            print(f"  🔍 Would move to: {new_path} | Error: {e}")
            return

        error_dir.mkdir(exist_ok=True)

        # Handle filename conflicts
        if new_path.exists():
            base = path.stem
            ext = path.suffix
            idx = 1
            while new_path.exists():
                new_path = error_dir / f"{base}_{idx}{ext}"
                idx += 1

        try:
            path.rename(new_path)
            print(f"  ⚠️  Moved to: {new_path} | Error: {e}")
        except OSError as move_error:
            print(f"  ❌ Failed to move {path}: {move_error}")


def get_files_to_process(paths: List[str]) -> List[Path]:
    """Collect Python files from arguments or current directory."""
    files = []

    if paths:
        for path_str in paths:
            p = Path(path_str)
            if p.is_file() and p.suffix == ".py":
                files.append(p)
            elif p.is_dir():
                files.extend(get_pyfiles(p))
            else:
                print(f"⚠️  Skipping: {path_str} (not a .py file or directory)")
    else:
        files = get_pyfiles(Path.cwd())

    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)

    return unique_files


def process_files_mpf3(files: List[Path], dry_run: bool = False) -> None:
    """Process files using mpf3 (multiprocessing)."""
    total = len(files)

    # Create a wrapper function that mpf3 can call
    def wrapper(path):
        # We need to track the counter globally
        if not hasattr(wrapper, "counter"):
            wrapper.counter = 0
        wrapper.counter += 1
        # Pass the counter as a tuple
        process_file((path, wrapper.counter, total, dry_run))

    try:
        mpf3(wrapper, files)
    except Exception as e:
        print(f"⚠️  mpf3 failed: {e}")
        raise


def process_files_threadpool(files: List[Path], dry_run: bool = False) -> None:
    """Process files using ThreadPoolExecutor."""
    total = len(files)

    def worker(path, idx):
        process_file((path, idx, total, dry_run))

    with ThreadPoolExecutor(max_workers=min(cpu_count() * 2, len(files))) as executor:
        futures = {executor.submit(worker, path, idx): path for idx, path in enumerate(files, 1)}

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                path = futures[future]
                print(f"  ❌ Unexpected error processing {path}: {e}")


def process_files_multiprocessing(files: List[Path], dry_run: bool = False) -> None:
    """Process files using multiprocessing Pool."""
    total = len(files)

    # Prepare arguments for each file
    args_list = [(path, idx, total, dry_run) for idx, path in enumerate(files, 1)]

    with Pool(processes=min(cpu_count(), len(files))) as pool:
        pool.map(process_file, args_list)


def process_files_sequential(files: List[Path], dry_run: bool = False) -> None:
    """Process files sequentially."""
    total = len(files)
    for idx, path in enumerate(files, 1):
        process_file((path, idx, total, dry_run))


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check Python files for syntax errors and move invalid ones to 'error' directories",
        epilog="Example: python script.py --dry-run /path/to/project",
    )
    parser.add_argument("paths", nargs="*", help="Files or directories to process (default: current directory)")
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Show what would be done without actually moving files"
    )
    parser.add_argument(
        "--parallel",
        "-p",
        choices=["sequential", "thread", "process", "mpf3"],
        default="mpf3",
        help="Parallel processing method (default: mpf3)",
    )

    args = parser.parse_args()

    # Collect files
    try:
        files = get_files_to_process(args.paths)
    except Exception as e:
        print(f"❌ Error collecting files: {e}")
        return 1

    if not files:
        print("ℹ️  No Python files found to process.")
        return 0

    print(f"📁 Found {len(files)} Python file(s) to process")
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be moved")
        print("-" * 50)

    # Process files with selected method
    try:
        if args.parallel == "sequential" or len(files) == 1:
            process_files_sequential(files, args.dry_run)
        elif args.parallel == "thread":
            process_files_threadpool(files, args.dry_run)
        elif args.parallel == "process":
            process_files_multiprocessing(files, args.dry_run)
        elif args.parallel == "mpf3":
            try:
                process_files_mpf3(files, args.dry_run)
            except Exception:
                print("⚠️  mpf3 failed, falling back to multiprocessing...")
                process_files_multiprocessing(files, args.dry_run)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error processing files: {e}")
        return 1

    if args.dry_run:
        print("-" * 50)
        print("🔍 DRY RUN COMPLETE - No files were moved")

    return 0


if __name__ == "__main__":
    sys.exit(main())
