#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import fsz, get_filez, gsz, mpf3, run_command


def process_file(fp):
    path = Path(path)
    if not fp.exists():
        return False
    if fp.suffix == ".c":
        cmd = f"clang {fp!s} -o {fp.with_suffix('')!s}"
    if fp.suffix == ".cpp":
        cmd = f"clang++ {fp!s} -o {fp.with_suffix('')!s}"
    ret, txt, _err = run_command(cmd)
    print(txt)
    return ret


def main() -> None:
    cwd = Path().cwd()
    start_size = gsz(cwd)
    files = []
    for path in get_filez(cwd):
        if path.is_file() and path.suffix in {".c", ".cpp"}:
            files.append(path)
    mpf3(process_file, files)
    print(f"{fsz(start_size - gsz(cwd))}")


if __name__ == "__main__":
    sys.exit(main())
