#!/data/data/com.termux/files/usr/bin/python

import os
import subprocess
from multiprocessing import cpu_count
from pathlib import Path

from rich.progress import Progress


def optimize_png(file_path):
    try:
        original_size = Path(file_path).stat().st_size
        subprocess.run(
            ["oxipng", "-o", "max", "--quiet", "--strip", "safe", file_path, "--force"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        optimized_size = Path(file_path).stat().st_size
        return original_size - optimized_size
    except subprocess.CalledProcessError:
        return 0


def find_png_files(directory):
    png_files = []
    for root, _, files in os.walk(directory):
        png_files.extend((os.path.join(root, file) for file in files if file.lower().endswith(".png")))
    return png_files


def main():
    current_dir = Path.cwd()
    png_files = find_png_files(current_dir)
    if not png_files:
        print("No PNG files found in the current directory or subdirectories.")
        return
    with Progress() as progress:
        task = progress.add_task("[cyan]Optimizing PNGs...", total=len(png_files))
        num_processes = min(cpu_count(), 8)
        with Pool(num_processes) as pool:
            for _ in pool.imap_unordered(optimize_png, png_files):
                progress.update(task, advance=1)
    total_space_freed = sum((optimize_png(fp) for fp in png_files)) / (1024 * 1024)
    print(f"\n[bold green]Total space freed: {total_space_freed:.2f} MB[/bold green]")


if __name__ == "__main__":
    main()
