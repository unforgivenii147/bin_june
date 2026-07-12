#!/data/data/com.termux/files/usr/bin/env python


from os import scandir as os_scandir
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_random_filename(length: int = 10) -> str:
    from random import choice
    from string import ascii_lowercase

    letters: str = ascii_lowercase
    return "".join(choice(letters) for _ in range(length))


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


def get_nobinary(path: str | Path) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


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


DEFAULT_OUTPUT_LEN = 8


def read_file(path: Path):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (IOError, OSError, UnicodeDecodeError):
        return None


def merge_files():
    cwd = Path.cwd()
    output_file = cwd / f"{get_random_filename()}.txt"
    files = sorted(get_nobinary(cwd))
    try:
        with output_file.open("w", encoding="utf-8") as fo:
            for i, file_path in enumerate(files):
                if str(file_path).startswith("."):
                    continue
                content = read_file(file_path)
                if content is None:
                    continue
                fo.write(f"\n# {file_path.name}\n")
                fo.write(content)
        print(f"\n✅ Merged {len(files)} files into: {output_file}")
        return output_file
    except IOError as e:
        print(f"Error writing output file: {e}")
        return None


if __name__ == "__main__":
    merge_files()
