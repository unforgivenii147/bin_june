#!/data/data/com.termux/files/home/.local/bin/python
"""Count lines of code, comments, and blanks across multiple languages."""

import sys
from pathlib import Path
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from dataclasses import dataclass
from typing import Dict, Set, Tuple
import re

LANGUAGE_PATTERNS: Dict[str, Dict[str, object]] = {
    "python": {
        "extensions": {".py"},
        "comment_single": "#",
        "comment_start": '"""',
        "comment_end": '"""',
    },
    "rust": {
        "extensions": {".rs"},
        "comment_single": "//",
        "comment_start": "/*",
        "comment_end": "*/",
    },
    "c": {
        "extensions": {".c", ".h"},
        "comment_single": "//",
        "comment_start": "/*",
        "comment_end": "*/",
    },
    "cpp": {
        "extensions": {".cpp", ".cc", ".cxx", ".hpp", ".h++"},
        "comment_single": "//",
        "comment_start": "/*",
        "comment_end": "*/",
    },
    "javascript": {
        "extensions": {".js", ".jsx"},
        "comment_single": "//",
        "comment_start": "/*",
        "comment_end": "*/",
    },
    "typescript": {
        "extensions": {".ts", ".tsx"},
        "comment_single": "//",
        "comment_start": "/*",
        "comment_end": "*/",
    },
    "java": {
        "extensions": {".java"},
        "comment_single": "//",
        "comment_start": "/*",
        "comment_end": "*/",
    },
    "go": {
        "extensions": {".go"},
        "comment_single": "//",
        "comment_start": "/*",
        "comment_end": "*/",
    },
    "ruby": {
        "extensions": {".rb"},
        "comment_single": "#",
        "comment_start": "=begin",
        "comment_end": "=end",
    },
    "shell": {
        "extensions": {".sh", ".bash"},
        "comment_single": "#",
        "comment_start": None,
        "comment_end": None,
    },
    "sql": {
        "extensions": {".sql"},
        "comment_single": "--",
        "comment_start": "/*",
        "comment_end": "*/",
    },
    "html": {
        "extensions": {".html", ".htm"},
        "comment_single": None,
        "comment_start": "<!--",
        "comment_end": "-->",
    },
    "xml": {
        "extensions": {".xml"},
        "comment_single": None,
        "comment_start": "<!--",
        "comment_end": "-->",
    },
    "css": {
        "extensions": {".css"},
        "comment_single": None,
        "comment_start": "/*",
        "comment_end": "*/",
    },
    "json": {
        "extensions": {".json"},
        "comment_single": None,
        "comment_start": None,
        "comment_end": None,
    },
    "yaml": {
        "extensions": {".yaml", ".yml"},
        "comment_single": "#",
        "comment_start": None,
        "comment_end": None,
    },
    "markdown": {
        "extensions": {".md", ".markdown"},
        "comment_single": None,
        "comment_start": None,
        "comment_end": None,
    },
}


@dataclass
class FileStats:
    language: str
    file: str
    lines: int
    code: int
    comments: int
    blanks: int


def detect_language(ext: str) -> str | None:
    for lang, config in LANGUAGE_PATTERNS.items():
        if ext in config["extensions"]:
            return lang
    return None


def count_lines(file_path: str) -> FileStats | None:
    path = Path(file_path)
    ext = path.suffix.lower()
    lang = detect_language(ext)

    if not lang:
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    lines = content.split("\n")
    config = LANGUAGE_PATTERNS[lang]

    code_count = 0
    comment_count = 0
    blank_count = 0
    in_block_comment = False

    comment_start = config["comment_start"]
    comment_end = config["comment_end"]
    comment_single = config["comment_single"]

    for line in lines:
        stripped = line.strip()

        if not stripped:
            blank_count += 1
            continue

        if comment_start and comment_end:
            if in_block_comment:
                comment_count += 1
                if comment_end in line:
                    in_block_comment = False
                continue

            if comment_start in line:
                comment_count += 1
                in_block_comment = True
                if comment_end in line:
                    in_block_comment = False
                continue

        if comment_single and stripped.startswith(comment_single):
            comment_count += 1
            continue

        code_count += 1

    return FileStats(
        language=lang,
        file=str(path),
        lines=len(lines),
        code=code_count,
        comments=comment_count,
        blanks=blank_count,
    )


def get_files(targets: list[str]) -> list[str]:
    files = []

    if not targets:
        targets = ["."]

    for target in targets:
        path = Path(target)
        if path.is_file():
            files.append(str(path))
        elif path.is_dir():
            files.extend(str(f) for f in path.rglob("*") if f.is_file())

    return files


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else []
    files = get_files(targets)

    if not files:
        print("No files found")
        return

    with Pool(cpu_count()) as pool:
        results = [r for r in pool.imap_unordered(count_lines, files) if r]

    if not results:
        print("No supported files found")
        return

    by_language = defaultdict(lambda: {"files": 0, "lines": 0, "code": 0, "comments": 0, "blanks": 0})

    for stat in results:
        lang = stat.language
        by_language[lang]["files"] += 1
        by_language[lang]["lines"] += stat.lines
        by_language[lang]["code"] += stat.code
        by_language[lang]["comments"] += stat.comments
        by_language[lang]["blanks"] += stat.blanks

    print(f"{'Language':<15} {'Files':>8} {'Lines':>10} {'Code':>10} {'Comments':>10} {'Blanks':>10}")
    print("-" * 63)

    total_stats = {"files": 0, "lines": 0, "code": 0, "comments": 0, "blanks": 0}

    for lang in sorted(by_language.keys()):
        stats = by_language[lang]
        print(
            f"{lang:<15} {stats['files']:>8} {stats['lines']:>10} {stats['code']:>10} {stats['comments']:>10} {stats['blanks']:>10}"
        )
        for key in total_stats:
            total_stats[key] += stats[key]

    print("-" * 63)
    print(
        f"{'Total':<15} {total_stats['files']:>8} {total_stats['lines']:>10} {total_stats['code']:>10} {total_stats['comments']:>10} {total_stats['blanks']:>10}"
    )


if __name__ == "__main__":
    main()
