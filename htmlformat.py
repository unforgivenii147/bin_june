#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path

from bs4 import BeautifulSoup


from pathlib import Path
from os import scandir as os_scandir
from collections.abc import Callable, Iterable


def fsz(sz: float) -> str:
    sz = abs(int(sz))
    units = "B", "KB", "MB", "GB", "TB"
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
        "\033[5;92mNO CHANGE\033[0m"
        if delta == 0
        else (
            f"\033[5;92m{'-' if delta > 0 else '+'} \033[5;94m{fsz(abs(delta))}\033[0m | "
            f"\033[5;96m{after / before * 100:.1f}\033[5;95m%\033[0m"
        )
    )
    print(f"\n{path.name} | {msg}")


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


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
