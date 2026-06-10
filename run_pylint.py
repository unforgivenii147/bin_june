#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import get_pyfiles, runcmd


def process_file(fp) -> None:
    cmd = [
    path = Path(path)
        "pylint",
        f"{fp!s}",
        "--persistent=n",
        "--reports=n",
        "--output-format=parseable",
        "--msg-template='{C}:{line}:{column}:{obj}:{msg}:{msg_id}'",
        str(fp),
    ]
    return runcmd(cmd, show_output=True)


def main():
    cwd = Path.cwd()
    args = argv[1:]
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            if p.is_dir():
                files.extend(get_pyfiles(p))
    else:
        files = get_pyfiles(cwd)
    for f in files:
        process_file(f)


if __name__ == "__main__":
    sys.exit(main())
