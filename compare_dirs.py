#!/data/data/com.termux/files/usr/bin/env python

"""Module for compare_dirs.py."""

from __future__ import annotations

import os
import shlex
import stat
import sys
from hashlib import sha256
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

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


CHUNK_SIZE = 32768


def get_sha256(path: str | Path) -> str:
    path = Path(path)
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def write_shell_copy(script_path: Path, src_root: Path, dst_root: Path, only_dirs, only_files) -> None:
    with script_path.open("w", encoding="utf-8") as sh:
        sh.write("#!/bin/sh\n")
        for d in sorted(only_dirs):
            dst_dir = dst_root / d
            sh.write(f"mkdir -p {shlex.quote(str(dst_dir))}\n")
        for f in sorted(only_files):
            dst_file = dst_root / f
            src_file = src_root / f
            parent = dst_file.parent
            sh.write(
                f"""mkdir -p {shlex.quote(str(parent))} && cp -a {shlex.quote(str(src_file))} {shlex.quote(str(dst_file))}
"""
            )
    st = script_path.stat()
    script_path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> None:
    cwd = Path.cwd()
    dir1 = sys.argv[1].strip()
    dir2 = sys.argv[2].strip()
    first = Path(dir1).expanduser() if "~" in dir1 else Path(dir1)
    second = Path(dir2).expanduser() if "~" in dir2 else Path(dir2)
    f_files = [p.name for p in first.glob("*") if p.is_file()]
    [p.name for p in first.glob("*") if p.is_dir()]
    s_files = [p.name for p in second.glob("*") if p.exists() and p.is_file()]
    [p.name for p in second.glob("*") if p.is_dir()]
    common1 = [(Path(dir1).resolve() / p) for p in f_files if p in s_files]
    common2 = {str(Path(dir1).resolve() / p): str(Path(dir2).resolve() / p) for p in f_files if p in s_files}
    if common1:
        for k in common1:
            print(f"  - {k}")
    else:
        print("no common files")
        sys.exit(1)
    only_files_first = [p for p in f_files if p not in s_files]
    [p for p in s_files if p not in f_files]
    common_txt = cwd / "common.txt"
    common_txt.write_text("\n".join([str(p) for p in common1]))
    ans = input(f"delete from {dir1}  ? ")
    if ans == "y":
        for k, v in common2.items():
            if get_sha256(k) == get_sha256(v):
                print(f"the files are identical \n{k}\n{v}")
                Path(k).unlink()
            else:
                print(f"similar name filed:\n{k}\n{v}\n")
    cprint("only in first")
    for p in only_files_first:
        print(p)


if __name__ == "__main__":
    main()
