#!/data/data/com.termux/files/usr/bin/python

import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dh import BIN_EXT
from tqdm import tqdm

EXCLUDED_EXTENSIONS = BIN_EXT


def process_file(filepath):
    counter = Counter()
    try:
        with Path(filepath).open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    counter[line] += 1
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return counter


def collect_files_by_extension():
    ext_map = {}
    for root, _, filenames in os.walk(Path.cwd()):
        for fname in filenames:
            if fname.startswith("."):
                continue
            full_path = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower().lstrip(".")
            if ext in EXCLUDED_EXTENSIONS:
                continue
            if not ext:
                ext_map.setdefault(ext, []).append(full_path)
    return ext_map


def collect_lines_for_extension(ext, files):
    if not files:
        return
    global_counter = Counter()
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        for future in tqdm(as_completed(futures), total=len(futures), desc=f"Processing .{ext}  files"):
            global_counter.update(future.result())
    output_file = f"{ext}.txt"
    with Path(output_file).open("w", encoding="utf-8") as fo:
        for line, count in global_counter.most_common():
            if count >= 2:
                fo.write(line + "\n")
    print(f"Saved results to {output_file}")


def main():
    ext_map = collect_files_by_extension()
    if not ext_map:
        print("No eligible files found.")
        return
    for ext, files in ext_map.items():
        collect_lines_for_extension(ext, files)


if __name__ == "__main__":
    main()
