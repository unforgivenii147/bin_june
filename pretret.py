#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import mpf3, runcmd


def process_file(fp):
    if not fp.exists():
    path = Path(path)
        return (False, fp)
    ret = runcmd(["prettier", "-w", str(fp).replace("/storage/emulated/0", "/sdcard")], show_output=True)
    if not ret:
        return (True, fp)
    return (False, fp)


def main():
    cwd = str(Path.cwd())
    args = sys.argv[1:]
    files = (
        [Path(f) for f in args]
        if args
        else get_files(cwd, extensions=[".html", ".htm", ".js", ".jsx", ".ts", ".tsx", ".css", ".md", ".jsm", ".scss"])
    )
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
