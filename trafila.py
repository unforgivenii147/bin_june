#!/data/data/com.termux/files/usr/bin/env python

"""Module for trafila.py."""
from __future__ import annotations

import sys
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import trafilatura


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


try:
    import markdownify
except ImportError:
    markdownify = None

remove_orig = True


def process_file(path: str | Path) -> tuple[Path, bool]:
    path = Path(path)
    md_file = path.with_suffix(".md")

    if md_file.exists():
        return md_file, True

    try:
        html_content = path.read_text(encoding="utf-8")

        markdown = trafilatura.extract(
            html_content,
            output_format="markdown",
            include_links=True,
            include_images=True,
            include_tables=True,
            no_fallback=False,
        )

        if not markdown and markdownify:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, "html.parser")
            markdown = markdownify.markdownify(str(soup))

        if markdown and markdown.strip():
            md_file.write_text(markdown, encoding="utf-8")
            print(f"✓ Converted: {path.name} -> {md_file.name}")
            #            if remove_orig:
            #                path.unlink()
            return md_file, True

        print(f"✗ No content extracted from {path.name}")
        return path, False

    except Exception as e:
        print(f"✗ Error processing {path.name}: {e}")
        return path, False


def get_files(directory: Path, ext: list[str]) -> list[Path]:
    return [f for f in directory.rglob("*") if f.suffix in ext]


def mpf3(func, items: list[Path]) -> None:
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(func, items))
        successful = sum(1 for _, success in results if success)
        print(f"\n✓ Successfully converted: {successful}/{len(items)}")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, [".html", ".htm", ".xhtml", ".xhtm"])
    numf = len(files)

    if numf == 0:
        print("No HTML files found.")
        sys.exit(1)

    if numf == 1:
        process_file(files[0])
        sys.exit(0)

    mpf3(process_file, files)
