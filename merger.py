#!/data/data/com.termux/files/home/.local/bin/python
"""Merge non-binary files from current directory into a single text file."""

from __future__ import annotations

from pathlib import Path
from random import choice
from string import ascii_lowercase
from typing import Optional

# Constants
CHUNK_SIZE: int = 8192
BINARY_THRESHOLD: float = 0.3
DEFAULT_OUTPUT_LEN: int = 10
# Extended to include common UTF-8 continuation bytes (0x80-0xBF)
TEXT_CHARS: bytearray = bytearray(
    list(range(32, 127))  # ASCII printable
    + list(range(0x80, 0x100))  # Extended ASCII/UTF-8 continuation bytes
    + [ord(c) for c in "\n\r\t\b"]
)


def get_files(path: Path, ext: Optional[list[str]] = None) -> list[Path]:
    files: list[Path] = []
    for root, dirs, filenames in path.walk(top_down=False):
        for filename in filenames:
            file_path = Path(root) / filename
            if file_path.is_symlink() or not file_path.is_file():
                continue
            if ".git" in file_path.parts:
                continue
            if is_binary(file_path):
                continue
            if ext is not None:
                if file_path.suffix in set(ext):
                    files.append(file_path)
            else:
                files.append(file_path)
    return files


def get_random_filename(length: int = DEFAULT_OUTPUT_LEN) -> str:
    return "".join(choice(ascii_lowercase) for _ in range(length))


def is_binary(path: Path) -> bool:
    """Check if a file is binary by reading a chunk and analyzing byte content."""
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)

        if not chunk:  # Empty files are not binary
            return False

        if b"\x00" in chunk:  # Null byte strongly indicates binary
            return True

        # Try to decode as UTF-8 first
        try:
            chunk.decode("utf-8")
            return False  # Successfully decoded, not binary
        except UnicodeDecodeError:
            pass  # Not valid UTF-8, check further

        # Count non-text characters
        nontext = sum(1 for byte in chunk if byte not in TEXT_CHARS)
        return (nontext / len(chunk)) > BINARY_THRESHOLD

    except (OSError, PermissionError):
        return True


def get_nobinary(path: Path) -> list[Path]:
    """Get all non-binary files. Note: is_binary check is now in get_files."""
    return get_files(path)  # is_binary check is already done in get_files


def read_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return None


def should_skip_file(file_path: Path, cwd: Path) -> bool:
    """Skip hidden files and directories."""
    try:
        relative_parts = file_path.relative_to(cwd).parts
    except ValueError:
        return True  # Skip if can't get relative path

    if any(part.startswith(".") for part in relative_parts):
        return True
    return bool(file_path.name.startswith("."))


def merge_files() -> Optional[Path]:
    cwd = Path.cwd()
    output_file = cwd / f"{get_random_filename()}.txt"

    files = [f for f in get_nobinary(cwd) if f != output_file]
    files.sort()

    if not files:
        print("ℹ️  No non-binary files found to merge.")
        return None

    try:
        total_size = 0
        file_count = 0
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
                file_count += 1

        if total_size == 0:
            output_file.unlink()
            print("ℹ️  No content to merge (all files were empty or skipped).")
            return None

        print(f"✅ Merged {file_count} files ({total_size:,} bytes) into: {output_file}")
        return output_file

    except OSError as e:
        print(f"❌ Error writing output file: {e}")
        if output_file.exists():
            output_file.unlink()
        return None


if __name__ == "__main__":
    merge_files()
