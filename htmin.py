#!/data/data/com.termux/files/usr/bin/env python
import sys
from collections import deque
from collections.abc import Callable, Iterable
from os import scandir as os_scandir
from pathlib import Path
import htmlmin


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


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)((delayed(process_function)(file_str, **kwargs) for file_str in file_strings))


def process_file(path: str | Path) -> None:
    path = Path(path)
    try:
        orig = path.read_text(encoding="utf-8")
        code = htmlmin.minify(orig, remove_comments=True)
        if len(code) != len(orig):
            path.write_text(code, encoding="utf-8")
            print(f"[OK] {path.name}")
            return
    except Exception:
        print(f"[ERR] {path.name}")
        return


def main() -> None:
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".html", ".htm", ".xhtml", ".mhtml"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
