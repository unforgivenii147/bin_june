#!/data/data/com.termux/files/usr/bin/env python
import compileall
import os
import sys
from collections.abc import Callable
from os import scandir as os_scandir
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


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
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > 0.3
    except Exception:
        return True


def get_pyfiles(path: str | Path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        if path.suffix == ".py":
            return [path]
        if not path.suffix and not path.name.startswith(".") and is_python_file(path):
            return [path]
        return []

    if not path.is_dir():
        return []

    pyfiles = []
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
                        p = Path(entry.path)
                        if p.suffix == ".py":
                            pyfiles.append(p)
                        elif not p.suffix and not p.name.startswith(".") and is_python_file(p):
                            pyfiles.append(p)
        except (PermissionError, OSError):
            continue

    return sorted(pyfiles)


REMOVE_ORIG = False
LEGACY_MODE = False
OPTIMIZE_LEVEL = 2


def process_file(path) -> bool | None:
    path = Path(path)
    if not path.exists():
        return False
    if ".git" in path.parts:
        return None
    if path.is_dir():
        for f in path.rglob("*.py"):
            process_file(f)
    if path.is_file() and (not path.is_symlink()):
        pyc_file = path.with_suffix(".pyc") if LEGACY_MODE else None
        if pyc_file and pyc_file.exists():
            pyc_file.unlink()
        compileall.compile_file(path, optimize=OPTIMIZE_LEVEL, legacy=LEGACY_MODE)
        if REMOVE_ORIG:
            path.unlink()
        return True
    return False


def main():
    global REMOVE_ORIG, LEGACY_MODE, OPTIMIZE_LEVEL
    os.environ["PYTHONPYCACHEPREFIX"] = "__pycache__"
    cwd = Path.cwd()
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-o", "--optimize"):
            if i + 1 < len(args):
                try:
                    OPTIMIZE_LEVEL = int(args[i + 1])
                    if OPTIMIZE_LEVEL not in (0, 1, 2):
                        print(f"Error: Optimize level must be 0, 1, or 2 (got {OPTIMIZE_LEVEL})")
                        return 1
                    i += 2
                    continue
                except ValueError:
                    print(f"Error: Invalid optimize level: {args[i + 1]}")
                    return 1
            else:
                print("Error: -o/--optimize requires an argument (0, 1, or 2)")
                return 1
        elif arg in ("-l", "--legacy"):
            LEGACY_MODE = True
            i += 1
        elif arg in ("-h", "--help"):
            print("Usage: python script.py [options] [files/directories]")
            print("Options:")
            print("  -o, --optimize LEVEL  Set optimization level (0, 1, or 2, default: 0)")
            print("  -l, --legacy        Create legacy .pyc file beside original file")
            print("  -h, --help          Show this help message")
            print("  files/directories   Files or directories to process (default: current directory)")
            return 0
        else:
            break
    files = []
    if i < len(args):
        for arg in args[i:]:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_pyfiles(p))
    else:
        files = get_pyfiles(cwd)
    if not files:
        print("No Python files found to process")
        return 0
    if len(files) == 1:
        process_file(files[0])
        return 0
    mpf3(process_file, files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
