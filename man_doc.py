#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import gzip
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile

from dh import cprint, get_files, runcmd
from dh.jobutils import mpf3


def safe_run(path) -> bool:
    path = Path(path)
    is_gzipped = path.suffix == ".gz"
    if is_gzipped:
        with NamedTemporaryFile(mode="w", suffix=path.stem, delete=False) as tmp:
            with gzip.open(path, "rt", encoding="utf8") as gz:
                tmp.write(gz.read())
            tmp_path = tmp.name
    else:
        tmp_path = str(path)
    try:
        cmd = ["mandoc", "-T", "html", tmp_path]
        res, txt, err = runcmd(cmd, show_output=False)
        if res != 0:
            print(f"Error running mandoc: {err}", file=sys.stderr)
            return False
        if is_gzipped:
            outpath = path.with_suffix(".html")
        else:
            outpath = path.with_suffix(".html")
        outpath.write_text(txt, encoding="utf8")
        if not is_gzipped:
            path.unlink()
        return True
    finally:
        if is_gzipped and Path(tmp_path).exists():
            Path(tmp_path).unlink()


def process_file(path) -> bool:
    path = Path(path)
    if not path.exists():
        return False
    print(f"{path.name}", end=" ")
    res = safe_run(path)
    if res:
        cprint("[✓] ", "cyan")
        return True
    cprint("[ERROR]", "red")
    return False


def main() -> None:
    args = sys.argv[1:]
    cwd = Path.cwd()
    base_exts = [".1", ".3", ".3am", ".3form", ".3menu", ".3ncurses", ".3readline", ".3t", ".4", ".5", ".7", ".8"]
    all_exts = base_exts + [f"{ext}.gz" for ext in base_exts]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=all_exts)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
