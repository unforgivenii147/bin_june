#!/data/data/com.termux/files/usr/bin/env python
import ast
import sys
import unicodedata
from collections import deque
from os import scandir as os_scandir
from pathlib import Path

import astor


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
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


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
