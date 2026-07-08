#!/data/data/com.termux/files/usr/bin/env python


import subprocess
import sys
from pathlib import Path
from dh import get_files


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
