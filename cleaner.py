#!/data/data/com.termux/files/usr/bin/env python


import re
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


def process_file(path) -> None:
    path = Path(path)
    ansi_re = re.compile(b"\\x1b\\[[?]?[0-9;]*[a-zA-Z]")
    osc_re = re.compile(b"\\x1b\\][^\\x07\\x1b]*[\\x07\\x1b]")
    misc_escape_re = re.compile(b"\\x1b[PX^_][^\\x1b]*\\x1b\\\\|\\x1b[@-_]")
    cr_re = re.compile(b"\\r\\n?|\\n\\r?")
    charset_re = re.compile(b"\\x1b[()][0-9a-zA-Z]")
    try:
        content = path.read_bytes()
        content = charset_re.sub(b"", content)
        content = osc_re.sub(b"", content)
        content = misc_escape_re.sub(b"", content)
        content = ansi_re.sub(b"", content)
        content = cr_re.sub(b"\n", content)
        text = content.decode("utf-8", errors="replace")
        cleaned_lines = []
        for line in text.splitlines(keepends=True):
            cleaned_line = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", line)
            cleaned_lines.append(cleaned_line)
        result = "".join(cleaned_lines)
        path.write_text(result, encoding="utf-8")
        print(f"✓  {path.name}")
    except Exception as e:
        print(f"✗ Error processing {path.name}: {e}", file=sys.stderr)
        return


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".log", ".txt", ".md"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
