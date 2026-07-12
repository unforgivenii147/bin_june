#!/data/data/com.termux/files/usr/bin/env python
import os
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_sha256(path: str | Path) -> str:
    from hashlib import sha256

    path = Path(path)
    if not path.exists() or not (size := path.stat().st_size):
        return ""
    h = sha256()
    try:
        with path.open("rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IOError):
        return ""


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


def get_path_dirs() -> list[Path]:
    path_env = os.environ.get("PATH", "").split("/")
    masonbin = "/data/data/com.termux/files/home/.local/share/nvim/mason/bin"
    found = [Path(p).expanduser() for p in path_env if p and p != masonbin]
    return [p for p in found if p.exists()]


def get_executables_in_dir(d: Path) -> list[Path]:
    try:
        return [f for f in d.iterdir() if f.is_file() and f.name != ".gitignore"]
    except PermissionError:
        print(f"Permission denied: {d}")
        return []


def main() -> None:
    dirs = [d for d in get_path_dirs() if d.is_dir()]
    executables: defaultdict[str, list[tuple[Path, str]]] = defaultdict(list)
    for d in dirs:
        for f in get_executables_in_dir(d):
            try:
                hash_ = get_sha256(f)
                executables[f.name].append((f, hash_))
            except PermissionError:
                print(f"Permission denied: {f}")
            except Exception as e:
                print(f"Error processing {f}: {e}")
    duplicates = {k: v for k, v in executables.items() if len(v) > 1}
    if not duplicates:
        print("No duplicates found.")
        return
    for name, items in sorted(duplicates.items()):
        cprint(f"Duplicate: {name}")
        for path, _ in sorted(items, key=lambda x: str(x[0])):
            print(f"  {path.name} in {path.parent.parent.name}/{path.parent.name}")
            print(f"  {path}")


if __name__ == "__main__":
    main()
