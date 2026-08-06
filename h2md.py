from __future__ import annotations
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
from markdownify import markdownify
from dh import get_files


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)((delayed(process_function)(file_str, **kwargs) for file_str in file_strings))


def process_file(path) -> None:
    path = Path(path)
    md_path = path.with_suffix(".md")
    content = path.read_text(encoding="utf8")
    markdownify(content)
    md_path.write_text(md_content, encoding="utf-8")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_files(p, ext=[".html"]))
    else:
        files.extend(get_files(p, ext=[".html"]))
    mpf3(process_file, files)
