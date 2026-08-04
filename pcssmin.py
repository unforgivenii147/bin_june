#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from collections import deque
from collections.abc import Callable, Iterable
from multiprocessing import get_context
from pathlib import Path
from typing import Any

from rcssmin import cssmin
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


def mpf_async(func: Callable[[Any], Any], items: Iterable[Any]):
    with get_context("spawn").Pool(MAX_WORKERS) as p:
        async_results = [p.apply_async(func, (item,)) for item in items]
        results = []
        for i, async_result in enumerate(async_results):
            try:
                results.append(async_result.get(timeout=30))
            except Exception as e:
                print(f"Item {i} failed: {e}")
                results.append(None)
        return results


mpf = mpf_async


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


def gext(path: str | Path) -> str:
    path = Path(path)
    suffs = path.suffixes
    if not suffs:
        return ""
    multipart_prefixes = {".tar", ".min", ".bundle", ".log", ".spec", ".test", ".d", ".module"}
    if len(suffs) > 1:
        if suffs[0] in multipart_prefixes:
            return "".join(suffs)
        if suffs[-1] in {".gz", ".xz", ".bz2", ".zst", ".lz"} and suffs[-2] == ".tar":
            return f".tar{suffs[-1]}"
        return suffs[-1]
    return suffs[0]


def process_file(path: Path) -> str:
    before = gsz(path)
    path = Path(path)
    print(f"{path.name}", end=" | ")
    after = before
    try:
        ext = gext(path)
        content = path.read_text(encoding="utf-8")
        if ext in {".css", ".min.css"}:
            minified = cssmin(content)
            after = len(minified)
        diff_size = len(content) - after
        if not diff_size:
            cprint("NO CHANGE", "green")
            return None
        path.write_text(minified, encoding="utf-8")
        after = gsz(path)
        diff_size = before - after
        if diff_size > 0:
            reduction = (before - after) / before * 100
            cprint(f"- {fsz(diff_size)} | reduction : {reduction:.3f}%", "cyan")
            return None
        if diff_size < 0:
            expantion = (after - before) / after * 100
            cprint(f"+ {fsz(diff_size)} | expantion : {expantion:.3f}%", "yellow")
            return None
    except Exception as e:
        return f"{path}: {e}"


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    files = get_files(cwd, ext=[".css", ".min.css"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    print(f"Found {len(files)} files. Starting multiprocessing...")
    mpf(process_file, files)
    after = gsz(cwd)
    dz = before - after
    if not dz:
        print("no change")
        sys.exit(1)
    if dz:
        ratio = dz / before * 100
        print(f"space reduced : {dz} ratio:{ratio}%")


if __name__ == "__main__":
    main()
