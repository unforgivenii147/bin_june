#!/data/data/com.termux/files/usr/bin/env python
import os
import sys
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def is_binary(path: Path | str) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def unique_path(path: Path | str) -> Path:
    path = _clean_fname(Path(path))
    if not path.exists():
        return path
    parent = path.parent
    suffixes = path.suffixes
    if suffixes:
        first_suffix_index = path.name.find(suffixes[0])
        stem = path.name[:first_suffix_index]
        full_suffix = "".join(suffixes)
    else:
        stem = path.name
        full_suffix = ""
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{full_suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def _clean_fname(path: Path) -> Path:
    from re import sub as re_sub

    clean_name = re_sub(r"(_\d+)+", "", path.name)
    return path.with_name(clean_name)


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


def runcmd(
    cmd: list[str], run_silently: bool = False, show_output: bool = True, timeout: float | None = None
) -> tuple[int, str, str]:
    from subprocess import DEVNULL as _DEVNULL
    from subprocess import TimeoutExpired as subprocess_TimeoutExpired
    from subprocess import run as subprocess_run
    from sys import stderr as sys_stderr
    from sys import stdout as sys_stdout

    if not cmd:
        msg = "cmd must be a non-empty list (e.g., ['ls', '-l'])"
        raise ValueError(msg)
    try:
        if run_silently:
            result = subprocess_run(cmd, stdout=_DEVNULL, stderr=_DEVNULL, timeout=timeout)
            return result.returncode, "", ""
        result = subprocess_run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout, stderr = result.stdout, result.stderr
        if show_output:
            if stdout:
                sys_stdout.write(stdout)
                sys_stdout.flush()
            if stderr:
                sys_stderr.write(stderr)
                sys_stderr.flush()
        return result.returncode, stdout, stderr
    except FileNotFoundError:
        msg = f"Command not found: '{cmd[0]}'"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 127, "", msg
    except PermissionError:
        msg = f"Permission denied: '{cmd[0]}'"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 126, "", msg
    except subprocess_TimeoutExpired:
        msg = f"Command timed out after {timeout}s: {' '.join(cmd)}"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 124, "", msg
    except Exception as e:
        msg = f"Unexpected error running '{cmd[0]}': {e}"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 1, "", msg


CONFIRM = "-y" in sys.argv


def fix_by_shebang(path) -> bool:
    if is_binary(path) or not path.stat().st_size:
        return False
    try:
        content = path.read_text(encoding="utf8")
    except:
        return False
    fl = content.splitlines()[0]
    if fl.startswith("#!") and ("bash" in fl or "/bin/sh" in fl):
        new_path = path.with_suffix(".sh")
        if new_path.exists():
            new_path = unique_path(new_path)
        path.rename(new_path)
        return True
    if fl.startswith("#!") and "python" in fl:
        new_path = path.with_suffix(".py")
        if new_path.exists():
            new_path = unique_path(new_path)
        path.rename(new_path)
        return True
    return False


def get_file_mime(path) -> str:
    _, txt, _ = runcmd(["file", "--brief", "--mime-type", str(path)], show_output=False)
    return txt


def safe_rename(old_path, new_path):
    base, ext = os.path.splitext(new_path)
    counter = 1
    while Path(new_path).exists():
        counter += 1
    cprint(f"{old_path} -> {new_path} ?")
    Path(old_path).rename(new_path)
    return new_path


def check_files(directory: Path):
    mismatched_files = []
    for root, _, files in os.walk(directory):
        for name in files:
            path = Path(root) / name
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            ext = path.suffix.lower()
            if ext in {".css", ".js"}:
                continue
            if fix_by_shebang(path):
                continue
            mime = get_file_mime(path)
            print(f"{name} --> {mime}")
            if mime:
                print(f"mime={mime}")
                expected_exts = MIME2EXT.get(mime.strip(), [])
                print(f"expected exts ={expected_exts}")
                if ".txt" in expected_exts:
                    continue
                if expected_exts and ext not in expected_exts:
                    new_path = None
                    new_ext = expected_exts[0]
                    new_name = path.stem + new_ext
                    print(f"new name = {new_name}")
                    new_path = Path(root) / new_name
                    if new_name == name:
                        continue
                    if new_path.exists():
                        new_path = unique_path(new_path)
                    if CONFIRM:
                        print(f"{path.suffix} -> {new_path.suffix}")
                        ans = input()
                        if ans == "y":
                            path.rename(new_path)
                    else:
                        path.rename(new_path)
                    mismatched_files.append((path, ext, mime, new_path))
    return mismatched_files


def main() -> None:
    cwd = Path.cwd()
    mismatches = check_files(cwd)
    if mismatches:
        print("Files with mismatched extensions:")
        for path, _ext, mime, new_path in mismatches:
            if new_path:
                print(f"\x1b[5;93m{path.name} {mime} \x1b[5;96m{new_path.name}]\x1b[0m")
            else:
                print(f"{path.name} -> \x1b[5m;94mdetected: {mime}\x1b[0m")
    else:
        cprint("no mismatch")


if __name__ == "__main__":
    main()
