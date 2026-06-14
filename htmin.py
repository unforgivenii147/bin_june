#!/data/data/com.termux/files/usr/bin/python

from pathlib import Path
import sys

import htmlmin
from dh import mpf3, get_files


def process_file(path: str | Path):
    path = Path(path)
    try:
        orig = path.read_text(encoding="utf-8")
        #        print(len(orig))
        #        code = orig
        code = htmlmin.minify(orig, remove_comments=True)
        #        print(len(code))
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
