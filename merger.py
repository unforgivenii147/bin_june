#!/data/data/com.termux/files/usr/bin/env python
"""Merge non-binary files from current directory into a single text file."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from random import choice
from string import ascii_lowercase

# Constants
CHUNK_SIZE: int = 8192
BINARY_THRESHOLD: float = 0.3
DEFAULT_OUTPUT_LEN: int = 10
SKIP_DIRS: set[str] = {".git", "__pycache__", ".venv", "node_modules", ".idea"}
TEXT_CHARS: bytearray = bytearray(range(32, 127)) + b"\n\r\t\b"


def get_files(path: Path, ext: list[str] | None = None) -> list[Path]:
    queue = deque([path])
    files: list[Path] = []

    while queue:
        current = queue.popleft()
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            continue

        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir():
                if item.name not in SKIP_DIRS:
                    queue.append(item)
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


def get_random_filename(length: int = DEFAULT_OUTPUT_LEN) -> str:
    return "".join(choice(ascii_lowercase) for _ in range(length))


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)

        if not chunk:  # Empty files are not binary
            return False

        if b"\x00" in chunk:  # Null byte = binary
            return True

        # Count non-text characters
        nontext = sum(1 for byte in chunk if byte not in TEXT_CHARS)
        return (nontext / len(chunk)) > BINARY_THRESHOLD

    except (OSError, PermissionError):
        return True


def get_nobinary(path: Path) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


def read_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return None


def should_skip_file(file_path: Path, cwd: Path) -> bool:
    if any(part.startswith(".") for part in file_path.relative_to(cwd).parts):
        return True
    if file_path.name.startswith("."):
        return True
    return False


def merge_files() -> Path | None:
    cwd = Path.cwd()
    output_file = cwd / f"{get_random_filename()}.txt"

    files = [f for f in get_nobinary(cwd) if f != output_file]
    files.sort()

    if not files:
        print("ℹ️  No non-binary files found to merge.")
        return None

    try:
        total_size = 0
        with output_file.open("w", encoding="utf-8") as fo:
            for file_path in files:
                if should_skip_file(file_path, cwd):
                    continue

                content = read_file(file_path)
                if content is None or not content.strip():
                    continue

                relative_path = file_path.relative_to(cwd)
                fo.write(f"# File: {relative_path}\n")
                fo.write(content)
                fo.write("\n")
                total_size += len(content)

        if total_size == 0:
            output_file.unlink()
            print("ℹ️  No content to merge (all files were empty or skipped).")
            return None

        print(f"✅ Merged {len(files)} files ({total_size:,} bytes) into: {output_file}")
        return output_file

    except OSError as e:
        print(f"❌ Error writing output file: {e}")
        if output_file.exists():
            output_file.unlink()
        return None


if __name__ == "__main__":
    merge_files()
