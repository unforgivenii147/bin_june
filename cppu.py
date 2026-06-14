#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import cprint, fsz, get_files, gsz, mpf3, runcmd

MAX_QUEUE = 16
EXT = [".java", ".c", ".cpp", ".cxx", ".cc", ".h", ".hh", ".hpp", ".hxx", ".js", ".json"]


def process_file(path) -> bool:
    path = Path(path)
    before = gsz(path)
    print(f"{path.name} ", end=" ")
    try:
        runcmd(["clang-format", "-i", "--style=LLVM", str(path)], show_output=False)
        size_diff = before - gsz(path)
        if not size_diff:
            cprint("[NO CHANGE]", "magenta")
        elif size_diff > 0:
            cprint(f"+ {fsz(size_diff)}", "cyan")
        elif size_diff < 0:
            cprint(f"- {fsz(size_diff)}", "green")
        del size_diff
        del before
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        del res
        del size_diff
        del before
        cprint(f"[ERR] {res.stderr!s}", "yellow")
        return False


def main() -> None:
    cfiles: list = []
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    cfiles = [Path(arg) for arg in args] if args else get_files(cwd, ext=EXT)
    all_count = len(cfiles)
    cprint(f"{all_count} files found", "cyan")
    if all_count == 1:
        process_file(cfiles[0])
        sys.exit(0)
    mpf3(process_file, cfiles)
    after = gsz(cwd)
    diffsize = before - gsz(cwd)
    print(f"space change: {fsz(diffsize)}")


if __name__ == "__main__":
    main()
