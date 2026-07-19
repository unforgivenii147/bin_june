#!/data/data/com.termux/files/usr/bin/env python
from __future__ import annotations

import os
import re
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def compress_python_file(filepath: str) -> None:
    content = Path(filepath).read_text(encoding="utf-8")
    content = re.sub(r"\"\"\".*?\"\"\"|'''.*?'''", "", content, flags=re.DOTALL)
    content = re.sub(r"#.*", "", content)
    lines = content.splitlines()
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    content = "\n".join(non_empty_lines)
    Path(filepath).write_text(content, encoding="utf-8")


def compress_python_files_in_directory(directory: str = ".") -> None:
    for filename in os.listdir(directory):
        if filename.endswith(".py"):
            filepath = os.path.join(directory, filename)
            print(f"Compressing {filepath}...")
            compress_python_file(filepath)
    print("Compression complete.")


if __name__ == "__main__":
    compress_python_files_in_directory(".")
