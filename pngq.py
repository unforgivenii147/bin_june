#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import os
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
from dh import get_fast
from dh import cprint


def runcmd(
    cmd: list[str],
    run_silently: bool = False,
    show_output: bool = True,
    timeout: float | None = None,
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


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


START_DIR = Path.cwd()
NUM_PROCESSES = 4


def process_file(path: str | Path) -> None:
    path = Path(path)
    before = gsz(path)
    try:
        cmd = [
            "pngquant",
            "--force",
            "--skip-if-larger",
            "--quality=60-70",
            "--strip",
            str(path),
            "--output",
            str(path),
        ]
        _ret, txt, _err = runcmd(cmd, show_output=False)
        if "skipping" in txt.lower():
            print(f" Skipped: {path.name}")
            return
        after = gsz(path)
        dz = before - after
        if not dz:
            print(f"✅ : {path.name} : (no change)")
            return
        ratio = (after / before) * 100
        print(f"✅ : {path.name}", end=" | ")
        cprint(f"{ratio:.1f} %")
        return
    except FileNotFoundError:
        print(
            "❌ Error: 'pngquant' command not found. Please ensure the 'pngquant' binary is installed and in your system PATH."
        )
    except Exception as e:
        print(f"❌ Error compressing {path}: {e}")
    return


def main() -> None:
    cwd = Path.cwd()
    for f in get_fast(cwd):
        if f.suffix in {".png", ".PNG"}:
            process_file(f)


if __name__ == "__main__":
    sys.exit(main())
