#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import get_files, mpf3, runcmd


def process_file(path: str | Path):
    path = Path(path)

    if not path.exists() or not path.stat().st_size:
        return (False, path)
    ret = runcmd(["prettier", "-w", str(path).replace("/storage/emulated/0", "/sdcard")], show_output=True)
    if not ret:
        return (True, path)
    return (False, path)


def main():
    cwd = str(Path.cwd())
    args = sys.argv[1:]
    files = (
        [Path(f) for f in args]
        if args
        else get_files(
            cwd, e=[".html", ".htm", ".js", ".jsx", ".ts", ".tsx", ".css", ".md", ".jsm", ".scss", ".tsm", ".coffee"]
        )
    )
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
