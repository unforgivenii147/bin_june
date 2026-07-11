#!/data/data/com.termux/files/usr/bin/env python
import argparse
import os
import sys
from os import scandir as os_scandir
from pathlib import Path
from time import perf_counter as pff
from pathlib import Path
from collections.abc import Callable, Iterable


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


SKIP_DIRS = [".git", ".ruff_cache", "__pycache__"]

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


def format_time(t: float) -> str:
    if t <= 0:
        return "0s"
    if t < 1:
        ms = t * 1000
        if ms < 1:
            return f"{ms * 1000:.0f}µs"
        return f"{ms:.2f}ms"
    if t < 60:
        return f"{t:.0f}s"
    if t < 3600:
        minutes = int(t // 60)
        secs = int(t % 60)
        return f"{minutes}m" + (f", {secs}s" if secs else "")
    if t < 86400:
        hours = int(t // 3600)
        remaining = t % 3600
        minutes = int(remaining // 60)
        secs = int(remaining % 60)
        result = f"{hours}h"
        if minutes:
            result += f", {minutes}m"
        if secs:
            result += f", {secs}s"
        return result
    if t < 86400 * 30:
        days = int(t // 86400)
        remaining = t % 86400
        hours = int(remaining // 3600)
        minutes = int(remaining % 3600 // 60)
        result = f"{days}d"
        if hours:
            result += f", {hours}h"
        if minutes:
            result += f", {minutes}m"
        return result
    months = t / (86400 * 30)
    if months < 1:
        return "less than 1 month"
    return f"{months:.2f} months"


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


def get_pyfiles(path: str | Path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        if path.suffix == ".py":
            return [path]
        if not path.suffix and not path.name.startswith(".") and is_python_file(path):
            return [path]
        return []

    if not path.is_dir():
        return []

    pyfiles = []
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
                        p = Path(entry)
                        if p.suffix == ".py":
                            pyfiles.append(p)
                        elif not p.suffix and not p.name.startswith(".") and is_python_file(p):
                            pyfiles.append(p)
        except (PermissionError, OSError):
            continue

    return sorted(pyfiles)


# ===== End of inlined code =====

MODE = "black"


def process_file(path: str | Path, mode: str = MODE) -> bool:
    stime = pff()
    path = Path(path)
    before: int = path.stat().st_size
    after: int = before
    try:
        original_code: str = path.read_text(encoding="utf-8")
        code = original_code
        match mode:
            case "autoflake":
                from autoflake import fix_code as fix_with_autoflake

                code = fix_with_autoflake(original_code, remove_all_unused_imports=True)
            case "isort":
                from isort import code as fix_with_isort

                code = fix_with_isort(original_code)
            case "black":
                from black import Mode as _Mode
                from black import TargetVersion as _tv
                from black import format_str

                code = format_str(original_code, mode=_Mode(target_versions={_tv.PY310, _tv.PY313}, line_length=120))
            case "autopep":
                from autopep8 import fix_code as fix_with_autopep

                code = fix_with_autopep(original_code, options={"aggressive": 2})
            case "yapf":
                from yapf.yapflib.yapf_api import FormatCode as fix_with_yapf

                code, _ = fix_with_yapf(original_code)
            case _:
                from black import Mode as _Mode
                from black import TargetVersion as _tv
                from black import format_str

                code = format_str(original_code, mode=_Mode(target_versions={_tv.PY310, _tv.PY313}, line_length=120))
        after = len(code)
        dsz = abs(before - after)
        etime = pff()
        if dsz:
            path.write_text(code, encoding="utf-8")
            ratio = dsz / before * 100
            print(f"{path.name} ", end=" ")
            cprint(f"({format_time(etime - stime)}) | {fsz(dsz)} | {ratio:.1f}%", "cyan")
            return True
        else:
            print(f"{path.name} ", end=" ")
            cprint(f"({format_time(etime - stime)}) | (no change)", "grey")
            return True
    except Exception as e:
        cprint("[ERROR]", "red", end=" ")
        print(f"{path.name}: {e}")
        return False


def main() -> None:
    global MODE
    p = argparse.ArgumentParser(description="Fast Python API-based formatter (Lazy Loading)")
    p.add_argument("-b", "--black", action="store_true", help="Use black style")
    p.add_argument("-a", "--autopep", action="store_true", help="Use autopep8 style")
    p.add_argument("-i", "--isort", action="store_true", help="Sort imports")
    p.add_argument("-r", "--raui", action="store_true", help="Autoflake cleanup")
    p.add_argument("-y", "--yapf", action="store_true", help="yapf formatter")
    args = p.parse_args()
    cwd = Path.cwd()
    files = get_pyfiles(cwd)
    if args.raui:
        MODE = "autoflake"
    elif args.black:
        MODE = "black"
    elif args.autopep:
        MODE = "autopep"
    elif args.isort:
        MODE = "isort"
    elif args.yapf:
        MODE = "yapf"
    else:
        MODE = "black"
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
