#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import ast
from os import scandir as os_scandir
from pathlib import Path
from dh import cprint, mpf3
from xxhash import xxh64_hexdigest

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
                        elif not p.suffix and (not p.name.startswith(".")) and is_python_file(p):
                            pyfiles.append(p)
        except (PermissionError, OSError):
            continue
    return sorted(pyfiles)


def process_file(path) -> tuple[str, Path]:
    path = Path(path)
    return (xxh64_hexdigest(ast.unparse(ast.parse(path.read_text(encoding="utf-8")))), path)


def main() -> None:
    cwd = Path.cwd()
    files = get_pyfiles(cwd)
    fd = {}
    results = mpf3(process_file, files)
    for result in results:
        hash, path = result
        fd.setdefault(hash, []).append(path)
    for h, p in fd.items():
        if len(p) > 1:
            print(f"files with hash: {h}")
            for path in p:
                print(f"  - {path}")
                path.unlink()
    deleted = 0
    for h, p in fd.items():
        if len(p) > 1:
            for path in p[1:]:
                deleted += 1
                if path.exists():
                    path.unlink()
    if deleted:
        cprint(f"{deleted} files removed.", "cyan")


if __name__ == "__main__":
    main()
