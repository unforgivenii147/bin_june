#!/data/data/com.termux/files/usr/bin/env python

"""Module for pyjtc.py."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def remove_comments_and_strings(content: str, filetype: str, keep_strings=False):
    if filetype in {"c", "cpp", "h", "hpp"}:
        content = re.sub(r"//.*", "", content)
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
        if not keep_strings:
            content = re.sub(r"\"[^\"]*\"", "", content)
            content = re.sub(r"'[^']*'", "", content)
    elif filetype == "py":
        content = re.sub(r"#.*", "", content)
        content = re.sub(r"\"\"\"[\s\S]*?\"\"\"", "", content)
        content = re.sub(r"'''[\s\S]*?'''", "", content)
        if not keep_strings:
            content = re.sub(r"\"[^\"]*\"", "", content)
            content = re.sub(r"'[^']*'", "", content)
    elif filetype == "sh":
        content = re.sub(r"#.*", "", content)
        if not keep_strings:
            content = re.sub(r"\"[^\"]*\"", "", content)
            content = re.sub(r"'[^']*'", "", content)
    return content


def process_file(filepath, inplace=False, keep_strings=False) -> None:
    p = Path(filepath)
    ext = p.suffix[1:].lower()
    if ext not in {"hpp", "h", "c", "cpp", "py", "sh"}:
        print(f"Unsupported file type: {ext}")
        return
    content = p.read_text(encoding="utf-8")
    cleaned = remove_comments_and_strings(content, ext, keep_strings)
    if inplace:
        p.write_text(cleaned, encoding="utf-8")
        print(f"File {filepath} cleaned and saved in-place.")
    else:
        print(f"--- Cleaned {filepath} ---\n{cleaned}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Remove comments and docstrings from code files, optionally keeping strings."
    )
    parser.add_argument("files", metavar="FILE", type=str, nargs="+", help="Files to process")
    parser.add_argument("-i", "--inplace", action="store_true", help="Edit files in-place")
    parser.add_argument("-s", "--strings", action="store_true", help="Keep strings in the output")
    args = parser.parse_args()
    for filepath in args.files:
        process_file(filepath, inplace=args.inplace, keep_strings=args.strings)
