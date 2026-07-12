#!/data/data/com.termux/files/usr/bin/env python


import subprocess
from multiprocessing import Pool, cpu_count
from pathlib import Path

from rich.progress import Progress


from pathlib import Path
from os import scandir as os_scandir


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def optimize_png(path) -> int:
    path = Path(path)
    try:
        original_size = path.stat().st_size
        subprocess.run(
            ["oxipng", "-o", "max", "--quiet", "--strip", "safe", str(path), "--force"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        optimized_size = path.stat().st_size
        return original_size - optimized_size
    except subprocess.CalledProcessError:
        return 0


def main() -> None:
    cwd = Path.cwd()
    png_files = get_files(cwd, ext=[".png"])
    if not png_files:
        print("No PNG files found in the current directory or subdirectories.")
        return
    with Progress() as progress:
        task = progress.add_task("[cyan]Optimizing PNGs...", total=len(png_files))
        num_processes = min(cpu_count(), 8)
        with Pool(8) as pool:
            for _ in pool.imap_unordered(optimize_png, png_files):
                progress.update(task, advance=1)
    total_space_freed = sum(optimize_png(path) for path in png_files) / (1024 * 1024)
    print(f"\n[bold green]Total space freed: {total_space_freed:.2f} MB[/bold green]")


if __name__ == "__main__":
    main()
