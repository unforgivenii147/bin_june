#!/data/data/com.termux/files/usr/bin/env python


import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from os import scandir as os_scandir
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


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


def fix_print_statements_manually(content):
    lines = content.split("\n")
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if re.search(r"\bprint\s+", line) and not is_in_string(line, "print"):
            if ">>" in line:
                line = re.sub(r"print\s+>>\s*(\w+)\s*,\s*(.+?)(?:\s*#.*)?$", "print(\\2, file=\\1)", line)
            else:
                line = re.sub(r"print\s+(.+?)(?:\s*#.*)?$", "print(\\1)", line)
            new_lines.append(line)
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


def is_in_string(line, text):
    in_string = False
    quote_char = None
    for i, char in enumerate(line):
        if char in ('"', "'") and (i == 0 or line[i - 1] != "\\"):
            if not in_string:
                in_string = True
                quote_char = char
            elif char == quote_char:
                in_string = False
                quote_char = None
        elif in_string and text in line[i - len(text) : i + 1]:
            return True
    return False


def process_file(path):
    path = Path(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        fixed_content = fix_print_statements_manually(content)
        if fixed_content != content:
            if not dry_run:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(fixed_content)
                print(f"  ✅ Manual conversion applied")
                result = subprocess.run(
                    ["ruff", "check", "--fix", "--select", "UP010", path], capture_output=True, text=True
                )
                if result.returncode == 0:
                    print(f"  ✅ Ruff applied additional fixes")
                return True
            else:
                print(f"  📝 Would convert {path}")
                return True
        else:
            print(f"  ⚠️  Could not automatically convert {path}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


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
                files.extend(get_files(p))
    else:
        files = get_files(cwd)
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)

    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
