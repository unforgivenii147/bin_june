#!/data/data/com.termux/files/usr/bin/env python

"""Module for bcss.py."""
from __future__ import annotations

import os
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path


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


def runcmd(
    cmd: list[str],
    run_silently: bool = False,
    show_output: bool = True,
    timeout: float | None = None,
) -> tuple[int, str, str]:
    from subprocess import DEVNULL as _DEVNULL, TimeoutExpired as subprocess_TimeoutExpired, run as subprocess_run
    from sys import stderr as sys_stderr, stdout as sys_stdout

    if not cmd:
        msg = "cmd must be a non-empty list (e.g., ['ls', '-l'])"
        raise ValueError(msg)
    try:
        if run_silently:
            result = subprocess_run(cmd, stdout=_DEVNULL, stderr=_DEVNULL, timeout=timeout)
            return (result.returncode, "", "")
        result = subprocess_run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout, stderr = (result.stdout, result.stderr)
        if show_output:
            if stdout:
                sys_stdout.write(stdout)
                sys_stdout.flush()
            if stderr:
                sys_stderr.write(stderr)
                sys_stderr.flush()
        return (result.returncode, stdout, stderr)
    except FileNotFoundError:
        msg = f"Command not found: '{cmd[0]}'"
        if show_output and (not run_silently):
            print(msg, file=sys_stderr)
        return (127, "", msg)
    except PermissionError:
        msg = f"Permission denied: '{cmd[0]}'"
        if show_output and (not run_silently):
            print(msg, file=sys_stderr)
        return (126, "", msg)
    except subprocess_TimeoutExpired:
        msg = f"Command timed out after {timeout}s: {' '.join(cmd)}"
        if show_output and (not run_silently):
            print(msg, file=sys_stderr)
        return (124, "", msg)
    except Exception as e:
        msg = f"Unexpected error running '{cmd[0]}': {e}"
        if show_output and (not run_silently):
            print(msg, file=sys_stderr)
        return (1, "", msg)


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


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


def process_file(path) -> bool | None:
    path = Path(path)
    before = gsz(path)
    if not path.exists():
        return False
    print(f"{path.name}", end=" ")
    cmd = ["cleancss", "--format", "beautify", str(path), "-o", str(path)]
    res, _, _err = runcmd(cmd, show_output=True)
    if not res:
        after = gsz(path)
        diffsize = before - after
        if not diffsize:
            cprint("[NO CHANGE]", "white")
            return
        if diffsize:
            ratio = diffsize / before * 100
            cprint(f"[OK] - {fsz(diffsize)} {abs(ratio):.1f}%", "cyan")
        return
    cprint("[ERROR]", "red")
    return


def main() -> None:
    args = sys.argv[1:]
    cwd = Path.cwd()
    before = gsz(cwd)
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".css", ".min.css"])
    _ = mpf3(process_file, files)
    diff_size = before - gsz(cwd)
    cprint(f"space freed : {fsz(diff_size)}", "green")


if __name__ == "__main__":
    sys.exit(main())
