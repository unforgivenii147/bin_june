#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
try:
    from dh import is_binary
except ImportError:

    def is_binary(path):
        return False


def count_lines_of_code(file_path: Path, lang) -> tuple[int, int, int]:
    if ".git" in str(file_path):
        return (0, 0, 0)
    if is_binary(str(file_path)):
        print(f"{file_path} is binary")
        return (0, 0, 0)
    with file_path.open(encoding="utf-8") as file:
        code_lines = 0
        comment_lines = 0
        blank_lines = 0
        for line in file:
            if not line.strip():
                blank_lines += 1
            elif re.match(COMMENT_PATTERNS.get(lang, ""), line):
                comment_lines += 1
            else:
                code_lines += 1
    return (code_lines, comment_lines, blank_lines)


def scan_directory(directory: str = "."):
    stats = {
        "total": {"code": 0, "comments": 0, "blank": 0},
        "languages": {lang: {"code": 0, "comments": 0, "blank": 0} for lang in LANG_EXTENSIONS},
    }
    base_path = Path(directory)
    for file_path in base_path.rglob("*"):
        if not file_path.is_file():
            continue
        file_extension = file_path.suffix.lower()
        if not file_extension:
            lang = get_language_from_shebang(str(file_path))
            if lang:
                code, comments, blanks = count_lines_of_code(file_path, lang)
                stats["languages"][lang]["code"] += code
                stats["languages"][lang]["comments"] += comments
                stats["languages"][lang]["blank"] += blanks
                stats["total"]["code"] += code
                stats["total"]["comments"] += comments
                stats["total"]["blank"] += blanks
                continue
        for lang, extensions in LANG_EXTENSIONS.items():
            if file_extension in extensions:
                code, comments, blanks = count_lines_of_code(file_path, lang)
                stats["languages"][lang]["code"] += code
                stats["languages"][lang]["comments"] += comments
                stats["languages"][lang]["blank"] += blanks
                stats["total"]["code"] += code
                stats["total"]["comments"] += comments
                stats["total"]["blank"] += blanks
                break
    return stats


def display_stats(stats) -> None:
    for lang_stats in stats["languages"].values():
        lang_stats["code"] > 0


if __name__ == "__main__":
    stats = scan_directory()
    display_stats(stats)
