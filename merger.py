#!/data/data/com.termux/files/usr/bin/env python
from collections import deque
from os import scandir as os_scandir
from pathlib import Path


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


def get_random_filename(length: int = 10) -> str:
    from random import choice
    from string import ascii_lowercase

    letters: str = ascii_lowercase
    return "".join((choice(letters) for _ in range(length)))


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


def get_nobinary(path: str | Path) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


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
