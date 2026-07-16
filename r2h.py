#!/data/data/com.termux/files/usr/bin/env python

import sys
from collections import deque
from collections.abc import Callable, Iterable
from multiprocessing import get_context
from os import scandir as os_scandir
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

from docutils.core import publish_parts

MAX_WORKERS = 4


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
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


def mpf_async(func: Callable[[Any], Any], items: Iterable[Any]):
    with get_context("spawn").Pool(MAX_WORKERS) as p:
        async_results = [p.apply_async(func, (item,)) for item in items]
        results = []
        for i, async_result in enumerate(async_results):
            try:
                results.append(async_result.get(timeout=30))
            except Exception as e:
                print(f"Item {i} failed: {e}")
                results.append(None)
        return results


def rst_to_html(content: str) -> str:
    try:
        parts = publish_parts(
            source=content,
            writer_name="html",
            settings_overrides={
                "initial_header_level": 2,
                "warning_stream": None,
                "report_level": 5,
            },
        )
        html_content = parts["html_body"]
        return html_content
    except Exception as e:
        print(f"Conversion error details: {e}")
        raise


def process_file(path):
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    html_content = rst_to_html(content)
    html_path = path.with_suffix(".html")
    html_path.write_text(html_content, encoding="utf-8")
    path.unlink()


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".rst"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf_async(process_file, files)


if __name__ == "__main__":
    main()
