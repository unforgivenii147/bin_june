#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import os
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import PageElement
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


def get_random_filename(length: int = 10) -> str:
    from random import choice
    from string import ascii_lowercase

    letters: str = ascii_lowercase
    return "".join(choice(letters) for _ in range(length))


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


def save_style(str1: list[PageElement]) -> None:
    if not str1 or len(str(str1)) < 2:
        return
    fn = "css/"
    fn += get_random_filename(10)
    fn += ".css"
    path = Path(fn)
    if path.exists():
        cprint(f"[{fn}] exists.", "red")
        path = unique_path(path)
    path.write_text("\n".join(list(str1)), encoding="utf-8")
    cprint(f"{[fn]} created.", "cyan")
    return


def process_file(path) -> bool:
    path = Path(path)
    html_content = path.read_text(encoding="utf-8")
    path = Path(path)
    soup = BeautifulSoup(html_content, "html.parser")
    styles = soup.find_all("style")
    if styles:
        cprint(f"{[path.name]} : {len(styles)} styles found.", "green")
        for style in styles:
            save_style(style.contents)
    return True


def main() -> None:
    outpath = Path("css")
    if not outpath.exists():
        outpath.mkdir(exist_ok=True)
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(arg) for arg in args] if args else get_files(cwd, ext=[".html", ".htm"])
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
