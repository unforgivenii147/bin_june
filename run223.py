#!/data/data/com.termux/files/usr/bin/env python
import subprocess
import sys
from collections import deque
from pathlib import Path


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


def run_2to3(file_path: Path) -> None:
    if not file_path.is_file():
        print(f"File not found: {file_path.name}")
        return
    try:
        subprocess.run(["2to3", "-w", "-n", "-f", "all", file_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running 2to3: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    cwd = Path.cwd()
    files = [Path(f) for f in args] if args else get_files(cwd, ext=[".py"])
    for file_path in files:
        run_2to3(file_path)
