#!/data/data/com.termux/files/usr/bin/env python
"""
Script to show various extensions in current directory with total size for each extension.
Uses pathlib and parallel processing for speedup.
"""

import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple


def get_file_info(file_path: Path) -> Tuple[str, int]:
    try:
        ext = file_path.suffix.lower() if file_path.suffix else "NO_EXTENSION"
        size = file_path.stat().st_size
        return ext, size
    except (OSError, PermissionError):
        return None, 0


def process_files_batch(file_paths: List[Path]) -> Dict[str, int]:
    ext_sizes = defaultdict(int)
    for file_path in file_paths:
        if file_path.is_file():
            ext, size = get_file_info(file_path)
            if ext is not None:
                ext_sizes[ext] += size
    return dict(ext_sizes)


def get_files_in_directory(directory: str = ".") -> List[Path]:
    path = Path(directory)
    files = []
    for file_path in path.rglob("*"):
        if ".git" in file_path.parts or file_path.is_symlink():
            continue
        if file_path.is_file():
            files.append(file_path)
    return files


def format_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def main():
    current_dir = "."
    print("-" * 60)
    print("Collecting files...")
    files = get_files_in_directory(current_dir)
    if not files:
        print("No files found in current directory.")
        return
    print(f"Found {len(files)} files")
    num_workers = 8
    print(f"Using {num_workers} parallel workers...")
    print("-" * 60)
    batch_size = max(1, len(files) // num_workers)
    file_batches = [files[i : i + batch_size] for i in range(0, len(files), batch_size)]
    ext_sizes_total = defaultdict(int)
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_batch = {
            executor.submit(process_files_batch, batch): batch_idx for batch_idx, batch in enumerate(file_batches)
        }
        completed = 0
        for future in as_completed(future_to_batch):
            try:
                batch_result = future.result()
                for ext, size in batch_result.items():
                    ext_sizes_total[ext] += size
                completed += 1
                if completed % max(1, len(file_batches) // 10) == 0:
                    print(f"Progress: {completed}/{len(file_batches)} batches processed")
            except Exception as e:
                print(f"Error processing batch: {e}")
    print("-" * 60)
    print("RESULTS:")
    print("-" * 60)
    if not ext_sizes_total:
        print("No files with recognized extensions found.")
        return
    sorted_extensions = sorted(ext_sizes_total.items(), key=lambda x: x[1], reverse=True)
    total_size = sum(ext_sizes_total.values())
    print(f"{'Extension':<20} {'Total Size':<15} {'Files':<10} {'Percentage'}")
    print("-" * 60)
    for ext, size in sorted_extensions:
        ext_files = sum(1 for f in files if f.suffix.lower() == ext or ext == "NO_EXTENSION" and f.suffix == "")
        percentage = size / total_size * 100 if total_size > 0 else 0
        display_ext = ext if ext != "NO_EXTENSION" else "(no extension)"
        print(f"{display_ext:<20} {format_size(size):<15} {ext_files:<10} {percentage:.1f}%")
    print("-" * 60)
    print(f"{'TOTAL':<20} {format_size(total_size):<15} {len(files):<10} 100.0%")
    print("-" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
