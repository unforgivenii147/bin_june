#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from pathlib import Path

from nudenet import NudeDetector
from dh import cprint


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
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


safe_path = Path("safe")
sexy_path = Path("sexy")
porn_path = Path("porn")
safe_path.mkdir(exist_ok=True)
sexy_path.mkdir(exist_ok=True)
porn_path.mkdir(exist_ok=True)


def check_porn(path: str):
    det = NudeDetector()
    return det.detect(path)


def process_file(path) -> None:
    path = Path(path)
    if "porn" in path.parts:
        return
    if "nude" in path.parts:
        return
    if "safr" in path.parts:
        return
    if "sexy" in path.parts:
        return
    result = check_porn(str(path))
    cprint(f"{path.name} is {result['class']} {result['score']}", "cyan")


if __name__ == "__main__":
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".jpg", ".jpeg", ".png", ".webp"])
    mpf3(process_file, files)
