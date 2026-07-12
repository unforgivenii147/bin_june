#!/data/data/com.termux/files/usr/bin/env python


import subprocess
import sys
from pathlib import Path


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
