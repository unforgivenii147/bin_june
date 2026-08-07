#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import argparse
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
from time import perf_counter as pff
from dh import cprint

CHUNK_SIZE = 1024 * 1024


def is_python_file(path: str | Path) -> bool:
    from ast import parse as ast_parse

    path = Path(path)
    if is_binary(path):
        return False
    if not path.stat().st_size:
        return False
    if path.is_file() and path.suffix == ".py":
        return True
    if not path.suffix:
        content = path.read_text(encoding="utf-8")
        if not content:
            return False
        if content.startswith("#!") and "python" in content[:100]:
            return True
        try:
            _ = ast_parse(content)
            return True
        except:
            return False
    return False


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
        nontext = sum((1 for b in chunk if b not in text_chars))
        return nontext / len(chunk) > 0.3
    except Exception:
        return True


def get_pyfiles(path: str | Path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        if path.suffix == ".py":
            return [path]
        if not path.suffix and (not path.name.startswith(".")) and is_python_file(path):
            return [path]
        return []
    if not path.is_dir():
        return []
    pyfiles = []
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
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
                if item.suffix == ".py":
                    pyfiles.append(item)
                elif not item.suffix and is_python_file(item):
                    pyfiles.append(item)
    return sorted(pyfiles)


from dh import fsz, mpf3

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
    sys.exit(main())
