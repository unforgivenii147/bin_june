#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from collections import deque
from multiprocessing import get_context
from pathlib import Path

from bs4 import BeautifulSoup
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


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


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


def process_file(file_path: Path) -> None:
    before = gsz(file_path)
    Path(path)
    try:
        html = file_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img"):
            img.decompose()
        for tag in soup.find_all(style=True):
            style = tag["style"]
            new_style = "; ".join(s for s in style.split(";") if "background-image" not in s).strip()
            if new_style:
                tag["style"] = new_style
            else:
                del tag["style"]
        clean_html = str(soup)
        file_path.write_text(clean_html, encoding="utf-8")
        after = gsz(file_path)
        print(f"{file_path.name}", end=" ")
        diffsize = before - after
        if diffsize == 0:
            cprint("NO CHANGE", "yellow")
        elif diffsize > 0:
            cprint(f" + {fsz(diffsize)}")
        elif diffsize < 0:
            cprint(f" - {fsz(diffsize)}")
    except:
        pass


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    if args:
        files = [Path(f) for f in args]
    else:
        files = get_files(cwd, ext=[".html", ".htm", ".md", ".rst", ".txt"])
    with get_context("spawn").Pool(8) as p:
        pending = deque()
        for f in files:
            pending.append(p.apply_async(process_file, (f,)))
            if len(pending) > 16:
                pending.popleft().get()
        while pending:
            pending.popleft().get()
    diff_size = before - gsz(cwd)
    print(f"space saved : {fsz(diff_size)}")


if __name__ == "__main__":
    main()
