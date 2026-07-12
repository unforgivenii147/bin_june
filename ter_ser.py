#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path


from pathlib import Path
from collections.abc import Callable, Iterable
from os import scandir as os_scandir


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


def rrs(path, before, after) -> None:
    delta = before - after
    msg = (
        "\033[5;92mNO CHANGE\033[0m"
        if delta == 0
        else (
            f"\033[5;92m{'-' if delta > 0 else '+'} \033[5;94m{fsz(abs(delta))}\033[0m | "
            f"\033[5;96m{after / before * 100:.1f}\033[5;95m%\033[0m"
        )
    )
    print(f"\n{path.name} | {msg}")


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
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
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


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


def runcmd(
    cmd: list[str], run_silently: bool = False, show_output: bool = True, timeout: (float | None) = None
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


EXT = [".js", ".jsx", ".jsm", ".jsc"]


def safe_run(path: Path) -> bool:
    cmd = ["terser", "--compress", "--mangle", "--", str(path)]
    res, txt, err = runcmd(cmd, show_output=False)
    if res != 0:
        print(f"Error running terser: {err}", file=sys.stderr)
        return False
    path.write_text(txt, encoding="utf8")
    return True


def process_file(path):
    path = Path(path)
    if "site-packages" in path.parts and "notebook" in path.parts:
        return
    before = gsz(path)
    if not path.exists() or not before:
        return
    if len(path.read_text().splitlines()) == 1:
        return
    if safe_run(path):
        after = gsz(path)
        rrs(path, before, after)
    return


def main():
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_files(p), ext=EXT)
    else:
        files = get_files(cwd, ext=EXT)
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
