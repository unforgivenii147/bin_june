#!/data/data/com.termux/files/usr/bin/env python

import sys
from collections import deque
from collections.abc import Callable, Iterable
from multiprocessing import get_context
from pathlib import Path
from typing import Any

MAX_WORKERS = 4


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


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


def mpf_async(func: Callable[[Any], Any], items: Iterable[Any]):
    with get_context("spawn").Pool(MAX_WORKERS) as p:
        async_results = [p.apply_async(func, (item,)) for item in items]
        results = []
        for i, async_result in enumerate(async_results):
            try:
                results.append(async_result.get(timeout=30))
            except Exception as e:
                print(f"Item {i} failed: {e}")
                results.append(None)
        return results


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


def process_file(path: Path) -> None:
    path = Path(path)
    temp_gs = path.with_name(f"temp_gs_{path.name}")
    size_before = path.stat().st_size
    print(f"{path.name} Before : {fsz(size_before)}")
    gs_cmd = [
        "gs",
        "-dBATCH",
        "-dColorConversionStrategy=/sRGB",
        "-dColorImageDownsampleType=/Bicubic",
        "-dColorImageResolution=85",
        "-dCompatibilityLevel=1.4",
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",
        "-dEmbedAllFonts=false",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dGrayImageResolution=85",
        "-dHaveTransparency=false",
        "-dMonoImageDownsampleType=/Bicubic",
        "-dMonoImageResolution=85",
        "-dNOPAUSE",
        "-dOptimize=true",
        "-dPDFSETTINGS=/screen",
        "-dSubsetFonts=true",
        "-sDEVICE=pdfwrite",
        f"-sOutputFile={temp_gs}",
        str(path),
    ]
    runcmd(gs_cmd, show_output=True)
    if temp_gs.exists():
        size_after = temp_gs.stat().st_size
        if size_after:
            print(f"{path.name} After  : {fsz(size_after)}")
            diff = size_before - size_after
            sign = "-" if diff >= 0 else "+"
            if size_after < size_before:
                temp_gs.replace(path)
                print(f"Saved  : {sign}{fsz(diff)}")
            else:
                print("original file is smaller")
                temp_gs.unlink(missing_ok=True)


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".pdf"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    mpf_async(process_file, files)
    after = gsz(cwd)
    dsz = before - after
    if dsz:
        print(f"space freed : {fsz(dsz)}")


if __name__ == "__main__":
    main()
