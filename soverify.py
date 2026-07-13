#!/data/data/com.termux/files/usr/bin/env python
import ctypes
import os
import subprocess
import sys
from collections import deque
from os import scandir as os_scandir
from pathlib import Path
from typing import List, Optional, Tuple
from loguru import logger


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
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


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


logger.remove()
logger.add(
    "/sdcard/soverify.log", level="ERROR", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", rotation="10 MB"
)


class CtypesVerifier:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.platform = sys.platform

    def log(self, message: str, level: str = "DEBUG") -> None:
        if self.verbose:
            getattr(logger, level.lower())(f"[CTYPES] {message}")

    def verify_so_file(self, file_path: Path) -> Tuple[bool, str]:
        if not file_path.exists():
            return (False, "File does not exist")
        if not file_path.is_file():
            return (False, "Not a regular file")
        try:
            lib = ctypes.CDLL(str(file_path), use_errno=True)
            err = ctypes.get_errno()
            if err:
                self.log(f"Warning: errno set to {err} for {file_path.name}")
            return (True, "ok")
        except OSError as e:
            error_msg = f"OSError: {e}"
            self.log(f"Failed to load {file_path.name}: {error_msg}", "ERROR")
            return (False, error_msg)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            self.log(f"Failed to load {file_path.name}: {error_msg}", "ERROR")
            return (False, error_msg)

    def verify_with_symbols(self, file_path: Path) -> Tuple[bool, dict]:
        can_load, msg = self.verify_so_file(file_path)
        symbol_info = {"can_load": can_load, "message": msg, "has_symbols": False, "symbol_count": 0}
        if not can_load:
            return (False, symbol_info)
        try:
            result = subprocess.run(["nm", str(file_path)], capture_output=True, timeout=10, text=True)
            if result.returncode == 0:
                lines = [line for line in result.stdout.split("\n") if line.strip()]
                symbol_info["symbol_count"] = len(lines)
                symbol_info["has_symbols"] = len(lines) > 0
                self.log(f"Found {len(lines)} symbols in {file_path.name}")
        except FileNotFoundError:
            self.log("'nm' command not found. Install binutils for symbol analysis", "WARNING")
        except subprocess.TimeoutExpired:
            self.log(f"Symbol extraction timed out for {file_path.name}", "WARNING")
        except Exception as e:
            self.log(f"Could not extract symbols from {file_path.name}: {e}", "ERROR")
        return (can_load, symbol_info)


def verify_single_file(file_path: Path) -> Optional[bool]:
    try:
        verifier = CtypesVerifier()
        success, message = verifier.verify_so_file(file_path)
        if success:
            logger.debug(f"✓ {file_path.name}: Valid")
            return True
        else:
            logger.error(f"✗ {file_path.name}: {message}")
            cprint(f"  ✗ {file_path}: {message}", "red")
            return False
    except Exception as e:
        logger.error(f"✗ {file_path.name}: Unexpected error - {e}")
        cprint(f"  ✗ {file_path}: Unexpected error - {e}", "red")
        return False


def collect_files(args: List[str]) -> List[Path]:
    if not args:
        return get_files(Path.cwd(), ext=[".so"])
    files = []
    for arg in args:
        path = Path(arg)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(get_files(path, ext=[".so"]))
        else:
            cprint(f"Warning: {path} does not exist", "yellow")
    return files


def main() -> None:
    files = collect_files(sys.argv[1:])
    if not files:
        cprint("No .so files found to verify", "yellow")
        return
    print(f"\nVerifying {len(files)} shared object file(s)...\n")
    valid_count = 0
    error_count = 0
    error_files = []
    for file_path in files:
        result = verify_single_file(file_path)
        if result is True:
            valid_count += 1
        elif result is False:
            error_count += 1
            error_files.append(file_path)
    print(f"\n{'=' * 50}")
    print(f"VERIFICATION SUMMARY")
    print(f"{'=' * 50}")
    print(f"Total files checked: {len(files)}")
    print(f"✓ Valid files:       {valid_count}")
    print(f"✗ Files with errors: {error_count}")
    if error_files:
        print(f"\n{'=' * 50}")
        print("FILES WITH ERRORS:")
        print(f"{'=' * 50}")
        for file_path in error_files:
            print(f"  ✗ {file_path}")
    logger.info(f"Verification complete: {valid_count} valid, {error_count} errors out of {len(files)} files")
    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    gil_state = ctypes.pythonapi.PyGILState_Ensure()
    try:
        main()
    except KeyboardInterrupt:
        cprint("\nVerification interrupted by user", "yellow")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        cprint(f"Fatal error: {e}", "red")
        sys.exit(1)
    finally:
        ctypes.pythonapi.PyGILState_Release(gil_state)
