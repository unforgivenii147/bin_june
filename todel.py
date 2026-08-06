#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
from collections import deque
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
from dh import get_files, get_nobinary


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


def delete_multiline_string_from_files(search_string: str) -> None:
    cwd = Path.cwd()
    files = get_nobinary(cwd)
    for path in files:
        content = path.read_text(encoding="utf-8")
        if search_string in content:
            new_content = content.replace(search_string, "")
        path.write_text(new_content, encoding="utf-8")


def read_string_to_delete(filename: str = "/sdcard/lic") -> str:
    path = Path(filename)
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    string_to_delete = read_string_to_delete()
    if string_to_delete:
        delete_multiline_string_from_files(string_to_delete)
