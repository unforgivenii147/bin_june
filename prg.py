#!/data/data/com.termux/files/usr/bin/env python
"""Ripgrep-like implementation in Python."""

import re
from pathlib import Path
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse


def walk_files(paths: list[str | Path]) -> Generator[Path, None, None]:
    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from (item for item in path.rglob("*") if item.is_file())


def search_file(file_path: Path, pattern: str) -> Generator[tuple[Path, int, str], None, None]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                matches = list(re.finditer(pattern, line))
                if matches:
                    colorized = colorize_line(line.rstrip("\n"), matches)
                    yield file_path, line_num, colorized
    except (OSError, IOError):
        pass


def colorize_line(line: str, matches) -> str:
    if not matches:
        return line

    parts = []
    last_end = 0

    for match in sorted(matches, key=lambda m: m.start()):
        start, end = match.span()
        parts.append(line[last_end:start])
        parts.append(f"\033[91m{line[start:end]}\033[0m")
        last_end = end

    parts.append(line[last_end:])
    return "".join(parts)


def ripgrep(paths: list[str | Path], pattern: str, max_workers: int = 4):
    def process_file(file_path: Path):
        return list(search_file(file_path, pattern))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_file, fp): fp for fp in walk_files(paths)}

        for future in as_completed(futures):
            for file_path, line_num, colorized_line in future.result():
                print(f"{file_path}({line_num}) {colorized_line}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ripgrep-like search tool")
    parser.add_argument("pattern", help="Search pattern (regex)")
    parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to search")
    parser.add_argument("-w", "--workers", type=int, default=4, help="Number of parallel workers")

    args = parser.parse_args()
    ripgrep(args.paths, args.pattern, args.workers)
