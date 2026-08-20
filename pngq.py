#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import sys
from pathlib import Path

from dh import get_files, gsz, mpf3, rrs, runcmd


def process_file(path: str | Path) -> None:
    path = Path(path)
    before = gsz(path)
    try:
        cmd = [
            "pngquant",
            "--force",
            "--skip-if-larger",
            "--quality=60-70",
            "--strip",
            str(path),
            "--output",
            str(path),
        ]
        _ret, txt, _err = runcmd(cmd, show_output=False)
        after = gsz(path)
        rrs(path, before, after)
        return
    except Exception:
        return


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".png", ".PNG"])
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
