#!/data/data/com.termux/files/home/.local/bin/python
"""
Script to show various extensions in current directory with file count for each extension.
Uses pathlib and parallel processing for speedup.
"""
from __future__ import annotations
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from dh import get_files
RECURSIVE = not "-n" in sys.argv
def process_files_batch(file_paths: list[Path]) -> dict[str, int]:
    ext_counts = defaultdict(int)
    for file_path in file_paths:
        ext = file_path.suffix.lower() if file_path.suffix else "NO_EXTENSION"
        ext_counts[ext] += 1
    return dict(ext_counts)
def main():
    cwd = Path.cwd()
    if not RECURSIVE:
        exts = {}
        extz = set()
        for path in cwd.iterdir():
            if path.is_dir() or path.is_symlink():
                continue
            if path.is_file():
                if path.suffix not in exts:
                    extz.add(path.suffix)
                    exts[path.suffix] = 1
                else:
                    exts[path.suffix] += 1
        for ext, count in exts.items():
            print(f" - {ext} : {count}")
        sys.exit(0)
    files = get_files(cwd)
    batch_size = max(1, len(files) // 8)
    file_batches = [files[i : i + batch_size] for i in range(0, len(files), batch_size)]
    ext_counts_total = defaultdict(int)
    with ProcessPoolExecutor(max_workers=8) as executor:
        future_to_batch = {
            executor.submit(process_files_batch, batch): batch_idx for batch_idx, batch in enumerate(file_batches)
        }
        for future in as_completed(future_to_batch):
            try:
                batch_result = future.result()
                for ext, count in batch_result.items():
                    ext_counts_total[ext] += count
            except Exception as e:
                print(f"Error processing batch: {e}")
    print("-" * 42)
    print("RESULTS:")
    print("-" * 42)
    if not ext_counts_total:
        print("No files with recognized extensions found.")
        return
    sorted_extensions = sorted(ext_counts_total.items(), key=lambda x: (-x[1], x[0]))
    max_ext_len = max(len(ext if ext != "NO_EXTENSION" else "(no extension)") for ext in ext_counts_total)
    for ext, count in sorted_extensions:
        display_ext = ext if ext != "NO_EXTENSION" else "(no extension)"
        print(f"{display_ext:<{max_ext_len + 2}} {count} file{'s' if count != 1 else ''}")
    print("-" * 42)
    print(f"{'TOTAL':<{max_ext_len + 2}} {len(files)} files")
    print("-" * 42)
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
