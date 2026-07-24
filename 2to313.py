#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import sys
from collections.abc import Callable
from lib2to3 import refactor
from os import scandir as os_scandir
from pathlib import Path

CHUNK_SIZE = 1024 * 1024

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


fixers = collect_fixers()


def collect_fixers():
    import pkgutil
    from lib2to3 import fixes

    fixer_names = []
    for _, modname, is_pkg in pkgutil.iter_modules(fixes.__path__, prefix="lib2to3.fixes."):
        if not is_pkg:
            fixer_names.append(modname)
    return fixer_names


def refactor_file(filepath: Path) -> None:
    options = {"print_function": True}
    tool = refactor.RefactoringTool(fixers, options)
    try:
        original = filepath.read_text()
        tree = tool.refactor_string(original, str(filepath))
        new_content = str(tree)
        if original == new_content:
            print(f"  nothing changed: {filepath}")
        else:
            filepath.write_text(new_content)
            print(f"  refactored:      {filepath}")
    except Exception as exc:
        print(f"  ERROR {filepath}: {exc}", file=sys.stderr)


def main() -> None:
    cwd = Path.cwd()
    files = get_pyfiles(cwd)
    mpf3(refactor_file, files)


if __name__ == "__main__":
    main()
