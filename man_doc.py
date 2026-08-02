#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import gzip
import os
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from dh import cprint


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
            elif item.is_file() and (
                ext is None
                or item.suffix in ext
                or (
                    item.suffixes[-2:] == [".1", ".gz"]
                    or item.suffixes[-2:] == [".3", ".gz"]
                    or item.suffixes[-2:] == [".4", ".gz"]
                    or (item.suffixes[-2:] == [".5", ".gz"])
                    or (item.suffixes[-2:] == [".7", ".gz"])
                    or (item.suffixes[-2:] == [".8", ".gz"])
                    or (item.suffixes[-2:] == [".3am", ".gz"])
                    or (item.suffixes[-2:] == [".3form", ".gz"])
                    or (item.suffixes[-2:] == [".3menu", ".gz"])
                    or (item.suffixes[-2:] == [".3ncurses", ".gz"])
                    or (item.suffixes[-2:] == [".3readline", ".gz"])
                    or (item.suffixes[-2:] == [".3t", ".gz"])
                )
            ):
                files.append(item)
    return files


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


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


def safe_run(path) -> bool:
    path = Path(path)
    is_gzipped = path.suffix == ".gz"
    if is_gzipped:
        with NamedTemporaryFile(mode="w", suffix=path.stem, delete=False) as tmp:
            with gzip.open(path, "rt", encoding="utf8") as gz:
                tmp.write(gz.read())
            tmp_path = tmp.name
    else:
        tmp_path = str(path)
    try:
        cmd = ["mandoc", "-T", "html", tmp_path]
        res, txt, err = runcmd(cmd, show_output=False)
        if res != 0:
            print(f"Error running mandoc: {err}", file=sys.stderr)
            return False
        if is_gzipped:
            outpath = path.with_suffix(".html")
        else:
            outpath = path.with_suffix(".html")
        outpath.write_text(txt, encoding="utf8")
        if not is_gzipped:
            path.unlink()
        return True
    finally:
        if is_gzipped and Path(tmp_path).exists():
            Path(tmp_path).unlink()


def process_file(path) -> bool:
    path = Path(path)
    if not path.exists():
        return False
    print(f"{path.name}", end=" ")
    res = safe_run(path)
    if res:
        cprint("[✓] ", "cyan")
        return True
    cprint("[ERROR]", "red")
    return False


def main() -> None:
    args = sys.argv[1:]
    cwd = Path.cwd()
    base_exts = [".1", ".3", ".3am", ".3form", ".3menu", ".3ncurses", ".3readline", ".3t", ".4", ".5", ".7", ".8"]
    all_exts = base_exts + [f"{ext}.gz" for ext in base_exts]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=all_exts)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
