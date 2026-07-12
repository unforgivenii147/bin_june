#!/data/data/com.termux/files/usr/bin/env python


import re
from concurrent.futures import ThreadPoolExecutor
from os import scandir as os_scandir
from pathlib import Path

from deep_translator import GoogleTranslator

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


DIRECTORY = "."
CHUNK_SIZE = 2000

non_english_pattern = re.compile(r"[^\x00-\x7F]")


def split_into_chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def translate_chunk(chunk: str) -> str:
    try:
        result = GoogleTranslator(source="auto", target="en").translate(chunk)
        print(result)
        print("*" * 33)
        print()
        return result
    except Exception as e:
        print(f"Chunk translation error: {e}")
        return chunk


def translate_file(path: Path) -> None:
    try:
        content = Path(path).read_text(encoding="utf-8")
    except:
        print(f"Skipping unreadable file: {path}")
        return
    if not non_english_pattern.search(content):
        return
    chunks = split_into_chunks(content, CHUNK_SIZE)
    with ThreadPoolExecutor(max_workers=16) as executor:
        translated_chunks = list(executor.map(translate_chunk, chunks))
    translated_text = "".join(translated_chunks)
    try:
        path.write_text(translated_text, encoding="utf-8")
        print(f"Translated → {path.name}")
    except Exception as e:
        print(f"Error writing {new_path}: {e}")


def process_directory(directory: str) -> None:
    files = get_nobinary(directory)
    for f in files:
        translate_file(f)


if __name__ == "__main__":
    process_directory(DIRECTORY)
