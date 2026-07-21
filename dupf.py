#!/data/data/com.termux/files/usr/bin/env python

"""Module for dupf.py."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from xxhash import xxh64

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


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
    units = "B", "KB", "MB", "GB", "TB"
    if sz == 0:
        return "0 B"
    i = min((int(sz).bit_length() - 1) // 10, len(units) - 1)
    value = sz / 1024**i
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


ATTRIBUTES = {
    "bold": 1,
    "dark": 2,
    "italic": 3,
    "underline": 4,
    "blink": 5,
    "reverse": 7,
    "concealed": 8,
    "strike": 9,
}

HIGHLIGHTS = {
    "on_black": 40,
    "on_grey": 40,
    "on_red": 41,
    "on_green": 42,
    "on_yellow": 43,
    "on_blue": 44,
    "on_magenta": 45,
    "on_cyan": 46,
    "on_light_grey": 47,
    "on_dark_grey": 100,
    "on_light_red": 101,
    "on_light_green": 102,
    "on_light_yellow": 103,
    "on_light_blue": 104,
    "on_light_magenta": 105,
    "on_light_cyan": 106,
    "on_white": 107,
}

COLORS = {
    "black": 30,
    "grey": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "light_grey": 37,
    "dark_grey": 90,
    "light_red": 91,
    "light_green": 92,
    "light_yellow": 93,
    "light_blue": 94,
    "light_magenta": 95,
    "light_cyan": 96,
    "white": 97,
}

RESET = "\x1b[0m"


def can_colorize(*, no_color=None, force_color=None):
    if no_color is not None and no_color:
        return False
    if force_color is not None and force_color:
        return True
    if os.environ.get("ANSI_COLORS_DISABLED"):
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "fileno"):
        return False
    try:
        return os.isatty(sys.stdout.fileno())
    except OSError:
        return sys.stdout.isatty()


def colored(text, color=None, on_color=None, attrs=None, *, no_color=None, force_color=None):
    result = str(text)
    if not can_colorize(no_color=no_color, force_color=force_color):
        return result
    fmt_str = "\x1b[%dm%s"
    rgb_fore_fmt_str = "\x1b[38;2;%d;%d;%dm%s"
    rgb_back_fmt_str = "\x1b[48;2;%d;%d;%dm%s"
    if color is not None:
        if isinstance(color, str):
            result = fmt_str % (COLORS[color], result)
        elif isinstance(color, tuple):
            result = rgb_fore_fmt_str % (color[0], color[1], color[2], result)
    if on_color is not None:
        if isinstance(on_color, str):
            result = fmt_str % (HIGHLIGHTS[on_color], result)
        elif isinstance(on_color, tuple):
            result = rgb_back_fmt_str % (on_color[0], on_color[1], on_color[2], result)
    if attrs is not None:
        for attr in attrs:
            result = fmt_str % (ATTRIBUTES[attr], result)
    result += RESET
    return result


def cprint(text, color=None, on_color=None, attrs=None, *, no_color=None, force_color=None, **kwargs):
    print(colored(text, color, on_color, attrs, no_color=no_color, force_color=force_color), **kwargs)


CHUNKSIZE = 32768


def should_skip(path: Path) -> bool:
    path = Path(path)
    return bool(
        path.is_symlink()
        or not path.stat().st_size
        or any(pat in path.parts for pat in (".git", "__pycache__", ".mypy_cache", ".ruff_cache"))
    )


def get_hash_file(path):
    if not path.exists() or not path.stat().st_size:
        return "", path
    h = xxh64()
    try:
        with path.open("rb") as f:
            while chunk := f.read(CHUNKSIZE):
                h.update(chunk)
        return h.hexdigest(), path
    except OSError:
        return "", path


def find_duplicates() -> None:
    cwd = Path.cwd()
    files_by_hash = defaultdict(list)
    duplicate_count = 0
    ptp = [path for path in cwd.rglob("*") if path.is_file() and not should_skip(path)]
    files_by_size = {}
    for p in ptp:
        try:
            size = p.stat().st_size
            files_by_size.setdefault(size, []).append(p)
        except OSError as e:
            print(f"Error getting size for {p}: {e}")
            continue
    paths_to_hash = []
    for size, paths in files_by_size.items():
        if len(paths) > 1:
            paths_to_hash.extend(paths)
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_path = {executor.submit(get_hash_file, path): path for path in paths_to_hash}
        for future in as_completed(future_to_path):
            hash_result, path = future.result()
            if hash_result is not None:
                files_by_hash.setdefault(hash_result, []).append(path)
    total = 0
    for hash, paths in files_by_hash.items():
        if len(paths) > 1:
            duplicate_count += len(paths) - 1
            print(f"hash {hash} :")
            for file_path in paths:
                relative_path = file_path.relative_to(cwd)
                cprint(f" - {relative_path}", "cyan")
                total += gsz(file_path)
    cprint(f"total : {fsz(total)}")


if __name__ == "__main__":
    find_duplicates()
