#!/data/data/com.termux/files/home/.local/bin/python
"""Merge non-binary files from current directory into a single text file."""

from __future__ import annotations

from pathlib import Path
from random import choice
from string import ascii_lowercase
from typing import Optional
from dh.fileutils import get_files
from dh.fileutils import get_random_filename
from dh.fileutils import is_binary
from dh.fileutils import get_nobinary

CHUNK_SIZE: int = 8192
BINARY_THRESHOLD: float = 0.3
DEFAULT_OUTPUT_LEN: int = 10

TEXT_CHARS: bytearray = bytearray(list(range(32, 127)) + list(range(0x80, 0x100)) + [ord(c) for c in "\n\r\t\b"])


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
        return True

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
