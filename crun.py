#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import sys
from collections.abc import Callable
from pathlib import Path
SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
def get_filez(root_dir: str | Path):
    from os import walk as os_walk
    visited_dirs: set[Path] = set()
    root_dir = Path(root_dir)
    if root_dir.is_dir():
        for dirpath, dirnames, filenames in os_walk(root_dir, topdown=True):
            base_path = Path(dirpath)
            for dirname in list(dirnames):
                full_path = base_path / dirname
                resolved_path = full_path.resolve()
                if should_skip(full_path) or resolved_path in visited_dirs:
                    dirnames.remove(dirname)
                visited_dirs.add(resolved_path)
            for filename in filenames:
                filepath = Path(dirpath) / filename
                if not should_skip(filepath):
                    yield filepath
    else:
        yield root_dir
from dh import fsz, mpf3, should_skip
def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total
def process_file(path):
    path = Path(path)
    if not path.exists():
        return False
    if path.suffix == ".c":
        cmd = f"clang {path!s} -o {path.with_suffix('')!s}"
    if path.suffix == ".cpp":
        cmd = f"clang++ {path!s} -o {path.with_suffix('')!s}"
    ret, txt, _err = run_command(cmd)
    print(txt)
    return ret
def main() -> None:
    cwd = Path().cwd()
    start_size = gsz(cwd)
    files = []
    for path in get_filez(cwd):
        if path.is_file() and path.suffix in {".c", ".cpp"}:
            files.append(path)
    mpf3(process_file, files)
    print(f"{fsz(start_size - gsz(cwd))}")
if __name__ == "__main__":
    sys.exit(main())
