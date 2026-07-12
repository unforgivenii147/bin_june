#!/data/data/com.termux/files/usr/bin/env python


import sys
from collections import deque
from multiprocessing import get_context
from pathlib import Path


from pathlib import Path
import os
from os import scandir as os_scandir
import sys

# WARNING: Source code for 'run_command' not found.

ATTRIBUTES = {"bold": 1, "dark": 2, "italic": 3, "underline": 4, "blink": 5, "reverse": 7, "concealed": 8, "strike": 9}

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


c_files = {".c", ".h", ".inc"}
cpp_files = {".cpp", ".cc", ".cxx", ".hpp", ".hpp11", ".hh", ".hxx"}


def validate_cpp(path: Path) -> tuple[bool, str]:
    cmd = ""
    if path.suffix in c_files:
        cmd = "clang -fsyntax-only str(path)"
    if path.suffix in cpp_files:
        cmd = "clang++ -fsyntax-only str(path)"
    ret, txt, err = run_command(cmd)
    return path, ret, txt, err


if __name__ == "__main__":
    args = sys.argv[1:]
    cwd = Path.cwd()
    files = (
        [Path(p) for p in args]
        if args
        else get_files(cwd, ext=[".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inc", "hpp11"])
    )
    results = []
    with get_context("spawn").Pool(8) as pool:
        pending = deque()
        for f in files:
            pending.append(pool.apply_async(validate_cpp, (f,)))
            if len(pending) > 8:
                results.append(pending.popleft().get())
        while pending:
            results.append(pending.popleft().get())
    for result in results:
        if int(result[1]) == 2:
            cprint(f"[✖] : {result[0].name} has error", "white")
        else:
            cprint(f"[✅] : {result[0].name} is ok", "cyan")
