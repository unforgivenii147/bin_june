#!/data/data/com.termux/files/usr/bin/env python


import ast
import sys
import unicodedata
from os import scandir as os_scandir
from pathlib import Path

import astor

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


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
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


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


BACKUP = False


def process_file(path) -> None:
    path = Path(path)
    if is_binary(path):
        return
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        if BACKUP:
            backup_file = path.with_suffix(path.suffix + ".bak")
            backup_file.write_text(content, encoding="utf-8")
        new_content = content
        if path.suffix == ".py":
            try:
                tree = ast.parse(content)
                new_content = astor.to_source(tree)
                path.write_text(new_content, encoding="utf-8")
                print(f"\x1b[0m[ \x1b[6;96m✓\x1b[0m ] {path.name} ")
                return
            except:
                print(f"\x1b[0m[ \x1b[6;96m✘\x1b[0m ] {path.name} ")
                return
        else:
            new_content = unicodedata.normalize("NFD", content)
            path.write_text(new_content, encoding="utf-8")
    except:
        return


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    backup = sys.argv[2] if len(sys.argv) > 2 else False
    files = [Path(arg) for arg in args] if args else get_files(cwd)
    for path in files:
        process_file(path)


if __name__ == "__main__":
    raise SystemExit(main())
