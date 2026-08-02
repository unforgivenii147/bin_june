#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import os
import re
import sys
from collections import deque
from collections.abc import Callable
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


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = ("B", "KB", "MB", "GB", "TB")
    if sz == 0:
        return "0 B"
    i = min((int(sz).bit_length() - 1) // 10, len(units) - 1)
    value = sz / 1024**i
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


blank_line = "\n"
IMAGE_RE = re.compile(r"^\s*(\.\.\s+image::|:target:|:alt:)", re.IGNORECASE)


def process_file(path: str | Path) -> None:
    path = Path(path)
    print(f"Processing {path.name}")
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"⚠️  Skipping {path}: {e}")
        return
    lines = content.splitlines(keepends=True)
    replaced_count = 0
    nl = []
    for line in lines:
        stripped = line.rstrip("\r\n")
        if stripped.lower().startswith("classifier"):
            nl.append("\n")
            replaced_count += 1
            continue
        if stripped.startswith("[![") or stripped.lower().startswith("project-url"):
            nl.append("\n")
            replaced_count += 1
            continue
        if stripped.startswith(
            (
                "Metadata-Version",
                "Home-page",
                "Author",
                "Maintainer",
                "License",
                "Platform",
                "Requires-Python",
                "Description-Content-Type",
                "Provides-Extra",
            )
        ):
            nl.append("\n")
            replaced_count += 1
            continue
        if IMAGE_RE.match(stripped):
            nl.append("\n")
            replaced_count += 1
            continue
        nl.append(line)
    if not replaced_count:
        return
    new_content = "".join(nl)
    if replaced_count:
        path.write_text(new_content, encoding="utf-8")
        print(f"✅ {path.name}", end="")
        cprint(f"{replaced_count}", "cyan")
        return
    print(f"❌ {path.name}: (no change)")


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(f) for f in args] if args else get_files(cwd, ext=[".metadata", ".md"])
    metafiles = list(cwd.rglob("METADATA"))
    if metafiles:
        files.extend(metafiles)
    print(f"{len(files)} files found.")
    _ = mpf3(process_file, files)
    diff_size = before - gsz(cwd)
    print(f"space saved : {fsz(diff_size)}")


if __name__ == "__main__":
    main()
