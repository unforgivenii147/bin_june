#!/data/data/com.termux/files/usr/bin/env python


import os
import sys
from pathlib import Path

import tree_sitter_python as tsp
from rapidfuzz import fuzz
from tree_sitter import Language, Parser

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
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


def get_filez(root_dir: str | Path):
    from os import walk as os_walk

    visited_dirs: set[Path] = set()
    root_dir = Path(root_dir)
    if root_dir.is_dir():
        for dirpath, dirnames, filenames in os_walk(root_dir, topdown=True):
            base_path = Path(dirpath)
            for dirname in list(dirnames):
                full_path = base_path / dirname
                resolved_path = full_path.resolve()
                if should_skip(full_path) or resolved_path in visited_dirs:
                    dirnames.remove(dirname)
                visited_dirs.add(resolved_path)
            for filename in filenames:
                filepath = Path(dirpath) / filename
                if not should_skip(filepath):
                    yield filepath
    else:
        yield root_dir


def should_skip(path: str | Path) -> bool:
    path = Path(path)
    return bool(path.is_symlink() or not SKIP_DIRS.isdisjoint(path.parts))


cwd = Path.cwd()
parser = Parser()
parser.language = Language(tsp.language())
VALID = {"import_statement", "import_from_statement"}


def process_file(path: Path) -> None:
    path = Path(path)
    src = path.read_bytes()
    tree = parser.parse(src)
    root = tree.root_node
    impoz = []
    results = [src[node.start_byte : node.end_byte].decode() for node in root.children if node.type in VALID]
    if results:
        for k in results:
            if k.startswith("import "):
                k = k.replace("import ", "")
                if " as " in k:
                    indx = k.index(" as ")
                    k = k[:indx]
                if "." in k:
                    indx = k.index(".")
                    k = k[:indx]
                if k not in impoz and (not k.startswith("_")):
                    impoz.append(k + "\n")
            elif k.startswith("from "):
                k = k.replace("from ", "")
                if k.startswith("."):
                    continue
                if " as " in k:
                    indx = k.index(" as ")
                    k = k[:indx]
                if "." in k:
                    indx = k.index(".")
                    k = k[:indx]
                if " import" in k:
                    indx = k.index(" import")
                    k = k[:indx]
                if k not in impoz and (not k.startswith("_")):
                    impoz.append(k + "\n")
    impoz = sorted(set(impoz))
    stdlib2 = list(STDLIB2)
    for x in impoz:
        x = x.strip().lower()
        if x in STDLIB2 and x not in {"io", "os", "pathlib", "ast", "urllib"}:
            cprint(f"{path.relative_to(cwd)}", "cyan")
            continue
        for v in stdlib2:
            v = v.lower()
            ratio = fuzz.ratio(x, v)
            if (
                ratio > 85
                and len(x) > 3
                and (len(v) > 3)
                and (
                    x
                    not in {
                        "io",
                        "os",
                        "pathlib",
                        "urllib",
                        "tkinter",
                        "pickle",
                        "string",
                        "queue",
                        "urllib3",
                        "configparser",
                        "copyreg",
                        "httplib2",
                    }
                )
            ):
                cprint(f"{path.relative_to(cwd)}", "yellow")
                cprint(f"{x} / {v} / {ratio}", "green")
                continue


def main() -> None:
    for path in get_filez(cwd):
        if path.is_symlink():
            continue
        if path.suffix == ".py":
            process_file(path)


if __name__ == "__main__":
    sys.exit(main())
