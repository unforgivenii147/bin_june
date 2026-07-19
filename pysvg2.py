#!/data/data/com.termux/files/usr/bin/env python
from __future__ import annotations

import sys
import tempfile
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
            elif item.is_file():
                if ext is None or item.suffix in ext:
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


def rrs(path, before, after) -> None:
    delta = before - after
    msg = (
        "\x1b[5;92mNO CHANGE\x1b[0m"
        if delta == 0
        else f"\x1b[5;92m{('-' if delta > 0 else '+')} \x1b[5;94m{fsz(abs(delta))}\x1b[0m | \x1b[5;96m{after / before * 100:.1f}\x1b[5;95m%\x1b[0m"
    )
    print(f"\n{path.name} | {msg}")


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


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


def process_file(path) -> None:
    path = Path(path)
    if "lazy" in path.parts:
        return
    if not path.exists():
        return
    before = path.stat().st_size
    tmp_out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp_out:
            tmp_out_path = tmp_out.name
        runcmd(["svgcleaner", str(path), str(tmp_out_path)], show_output=False)
        after = Path(tmp_out_path).stat().st_size
        if after:
            Path(tmp_out_path).replace(path)
            rrs(path, before, after)
            return
        return
    except Exception as e:
        return
    finally:
        if tmp_out_path and Path(tmp_out_path).exists():
            Path(tmp_out_path).unlink()


if __name__ == "__main__":
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".svg"])
    if not files:
        print("No SVG files found.")
        sys.exit(1)
    total_before = 0
    total_after = 0
    total_saved = 0
    results = mpf3(process_file, files)
