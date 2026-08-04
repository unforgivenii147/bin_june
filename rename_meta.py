#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
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


def unique_path(path: Path | str) -> Path:
    path = _clean_fname(Path(path))
    if not path.exists():
        return path
    parent = path.parent
    suffixes = path.suffixes
    if suffixes:
        first_suffix_index = path.name.find(suffixes[0])
        stem = path.name[:first_suffix_index]
        full_suffix = "".join(suffixes)
    else:
        stem = path.name
        full_suffix = ""
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{full_suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def _clean_fname(path: Path) -> Path:
    from re import sub as re_sub

    clean_name = re_sub("(_\\d+)+", "", path.name)
    return path.with_name(clean_name)


OUT_PATH = Path("/data/data/com.termux/files/home/tmp/metadata")


def process_file(path: Path) -> bool | None:
    pkgname = ""
    path = Path(path)
    pkgversion = ""
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    line1 = lines[1]
    line2 = lines[2]
    striped1 = line1.lower().strip()
    striped2 = line2.lower().strip()
    if striped1.startswith("name:"):
        pkgname = striped1.replace("name:", "").lstrip()
    if striped2.startswith("version:"):
        pkgversion = striped2.replace("version:", "").lstrip()
    if pkgversion and pkgname:
        outfn = Path(pkgname + "-" + pkgversion + ".metadata")
        outpath = OUT_PATH / outfn
        if outpath.exists():
            outpath = unique_path(outpath)
        outpath.write_text(content, encoding="utf-8")
        cprint(f"{outfn} created.", "green")
    elif pkgname and (not pkgversion):
        outfn = Path(pkgname + ".metadata")
        outpath = OUT_PATH / outfn
        content = path.read_text(encoding="utf-8")
        if outpath.exists():
            outpath = unique_path(outpath)
        content = path.read_text(encoding="utf-8")
        outpath.write_text(content, encoding="utf-8")
        cprint(f"{outfn} created.", "yellow")
    elif not pkgname and (not pkgversion):
        cprint(f"no data{path}", "cyan")
        input("what u wanna do?")
    return None


def main() -> None:
    cwd = Path.cwd()
    for path in get_files(cwd):
        if path.is_file() and (path.name == "METADATA" or path.suffix == ".metadata"):
            process_file(path)


if __name__ == "__main__":
    sys.exit(main())
