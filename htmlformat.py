#!/data/data/com.termux/files/usr/bin/env python
import sys
from collections import deque
from collections.abc import Callable, Iterable
from os import scandir as os_scandir
from pathlib import Path

from bs4 import BeautifulSoup


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


def rrs(path, before, after) -> None:
    delta = before - after
    msg = (
        "\x1b[5;92mNO CHANGE\x1b[0m"
        if delta == 0
        else f"\x1b[5;92m{('-' if delta > 0 else '+')} \x1b[5;94m{fsz(abs(delta))}\x1b[0m | \x1b[5;96m{after / before * 100:.1f}\x1b[5;95m%\x1b[0m"
    )
    print(f"\n{path.name} | {msg}")


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)((delayed(process_function)(file_str, **kwargs) for file_str in file_strings))


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


def process_file(path) -> None:
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, parser="lxml.parser", features="lxml")
    before = gsz(path)
    new_content = soup.prettify()
    after = len(new_content)
    rrs(path, before, after)


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".html", ".htm", ".xhtml"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    mpf3(process_file, files)
