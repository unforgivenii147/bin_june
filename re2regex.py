#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import argparse
import re
from concurrent.futures import ProcessPoolExecutor
from os import scandir as os_scandir
from pathlib import Path

CHUNK_SIZE = 1024 * 1024

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


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


NORMAL_IMPORT = "^import re\\b"
REGEX_IMPORT = "^import regex as re\\b"


def update_file(file_path, reverse: bool = False) -> str | None:
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = []
        changed = False
        search_pat = REGEX_IMPORT if reverse else NORMAL_IMPORT
        replacement = "import re" if reverse else "import regex as re"
        for line in lines:
            if not changed and re.match(search_pat, line):
                new_lines.append(re.sub(search_pat, replacement, line))
                changed = True
            else:
                new_lines.append(line)
        if changed:
            file_path.write_text("".join(new_lines), encoding="utf-8")
            return f"Updated: {file_path}"
        return None
    except Exception as e:
        return f"Error processing {file_path}: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Recursively swap 'import re' with 'import regex as re'")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse the replacement (regex as re -> re)")
    args = parser.parse_args()
    cwd = Path.cwd()
    py_files = get_pyfiles(cwd)
    print(f"Scanning {len(py_files)} files...")
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(update_file, py_files, [args.reverse] * len(py_files)))
    updates = [r for r in results if r]
    for msg in updates:
        print(msg)
    print(f"\nTask complete. Files modified: {len(updates)}")


if __name__ == "__main__":
    main()
