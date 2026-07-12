#!/data/data/com.termux/files/usr/bin/env python


import ast
import sys
from os import scandir as os_scandir
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


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


def detect_version(file_path: Path) -> None:
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    py2_score = 0
    py3_score = 0
    reasons = []
    try:
        tree = ast.parse(source)
        py3_score += 1
        reasons.append("Parsed successfully with Python 3 syntax.")
    except SyntaxError:
        print(f"{file_path.name}\nConfidence: High\nReason: Syntax error when parsed with Python 3.")
        return
    if "print " in source and "print(" not in source:
        py2_score += 2
        reasons.append("Uses print statement without parentheses (Python 2 style).")
    if "__future__" in source and "print_function" in source:
        py3_score += 2
        reasons.append("Uses 'from __future__ import print_function' (Python 3 compatibility).")
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.Await)):
            py3_score += 3
            reasons.append("Uses async/await syntax (Python 3 only).")
        if isinstance(node, ast.Try) and hasattr(node, "finalbody"):
            py3_score += 1
            reasons.append("Uses try/finally block (Python 3 syntax).")
        if isinstance(node, ast.FunctionDef):
            for arg in node.args.args:
                if hasattr(arg, "annotation") and arg.annotation is not None:
                    py3_score += 2
                    reasons.append("Uses function argument annotations (Python 3 feature).")
    if py2_score > py3_score:
        version = "2"
        confidence = "High" if py2_score - py3_score > 2 else "Medium"
    elif py3_score > py2_score:
        version = "3"
        confidence = "High" if py3_score - py2_score > 2 else "Medium"
    else:
        version = "3"
        confidence = "Low"
        reasons.append("No strong indicators found; defaulting to Python 3.")
    if version == "2":
        print(f"{file_path.name} : {version}\nConfidence: {confidence}\nReason(s):")


if __name__ == "__main__":
    args = sys.argv[1:]
    cwd = Path.cwd()
    files = [Path(f) for f in args] if args else get_files(cwd, ext=[".py"])
    for file_path in files:
        detect_version(file_path)
