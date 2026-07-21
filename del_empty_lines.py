#!/data/data/com.termux/files/usr/bin/env python

"""Module for del_empty_lines.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from binaryornot import is_binary

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


def get_filez(cwd: Path):
    for f in cwd.rglob("*"):
        if f.is_file() and not f.is_symlink():
            yield f


def process_file(path: Path) -> None:
    path = Path(path)
    removed = 0
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=False)
    newlines = []
    newlines = [line for line in lines if line.strip()]
    orig_len = len(lines)
    final_len = len(newlines)
    removed = orig_len - final_len
    if removed:
        print(f"{path.name}", end=" | ")
        cprint(f"{removed}", "blue")
        newcontent = "\n".join(newlines)
        path.write_text(newcontent, encoding="utf-8")
    else:
        print(f"{path.name}", end=" | ")
        cprint("NO CHANGE", "grey")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    if args:
        files = [Path(p) for p in args]
        for f in files:
            process_file(f)
    else:
        for f in get_filez(cwd):
            if not is_binary(f):
                process_file(f)
