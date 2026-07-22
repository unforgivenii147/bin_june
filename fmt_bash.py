#!/data/data/com.termux/files/usr/bin/env python

"""Module for fmt_bash.py."""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from subprocess import DEVNULL, TimeoutExpired, run

CHUNK_SIZE = 1024
SKIP_DIRS = {".git", "__pycache__"}


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    """Traverses directories using Python 3.12 Path.walk."""
    files = []
    # top_down=True allows modifying dirs in-place to skip unwanted folders
    for root, dirs, filenames in Path(path).walk(top_down=True, on_error=None):
        # Filter directories in-place to prevent walking into them
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for name in filenames:
            item = root / name
            if item.is_symlink():
                continue
            if ext is None or item.suffix in ext:
                files.append(item)
    return files


def runcmd(
    cmd: list[str],
    run_silently: bool = False,
    show_output: bool = True,
    timeout: float | None = None,
) -> tuple[int, str, str]:
    if not cmd:
        raise ValueError("cmd must be a non-empty list (e.g., ['ls', '-l'])")

    try:
        if run_silently:
            result = run(cmd, stdout=DEVNULL, stderr=DEVNULL, timeout=timeout)
            return (result.returncode, "", "")

        result = run(cmd, capture_output=True, text=True, timeout=timeout)
        if show_output:
            if result.stdout:
                sys.stdout.write(result.stdout)
            if result.stderr:
                sys.stderr.write(result.stderr)
        return (result.returncode, result.stdout, result.stderr)

    except FileNotFoundError:
        msg = f"Command not found: '{cmd[0]}'"
        if show_output and not run_silently:
            print(msg, file=sys.stderr)
        return (127, "", msg)
    except PermissionError:
        msg = f"Permission denied: '{cmd[0]}'"
        if show_output and not run_silently:
            print(msg, file=sys.stderr)
        return (126, "", msg)
    except TimeoutExpired:
        msg = f"Command timed out after {timeout}s: {' '.join(cmd)}"
        if show_output and not run_silently:
            print(msg, file=sys.stderr)
        return (124, "", msg)
    except Exception as e:
        msg = f"Unexpected error running '{cmd[0]}': {e}"
        if show_output and not run_silently:
            print(msg, file=sys.stderr)
        return (1, "", msg)


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > 0.3
    except Exception:
        return True


def has_shell_shebang(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            first = f.readline(256).decode("utf-8", errors="ignore").strip()
        return first.startswith("#!") and ("bash" in first or "sh" in first)
    except Exception:
        return False


def process_file(path_str: str) -> tuple[bool, str]:
    path = Path(path_str)
    print(f"Formatting:  {path.name}")
    res_code, _, stderr = runcmd(["shfmt", "-w", str(path)], show_output=True)
    if res_code != 0:
        print(f"  shfmt failed on {path.name}: {stderr.strip()}", file=sys.stderr)
        return (False, path_str)
    return (True, path_str)


def main() -> None:
    cwd = Path.cwd()

    # Fixed logic operator precedence
    files = [p for p in get_files(cwd) if (not p.suffix and has_shell_shebang(p)) or p.suffix == ".sh"]

    # Filter out binaries sequentially (fast metadata/head read)
    non_binary_files = [p for p in files if not is_binary(p)]

    if not non_binary_files:
        print("No shell files found to format.")
        return

    file_strings = [str(f) for f in non_binary_files]

    # Python Native parallel execution using ProcessPoolExecutor
    print(f"Processing {len(file_strings)} files...")
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(process_file, file_strings))

    # Print summary of failures
    failed = [Path(p_str).relative_to(cwd) for success, p_str in results if not success]
    if failed:
        print("\nFailed files:")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
