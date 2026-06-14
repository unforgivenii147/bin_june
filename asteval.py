#!/data/data/com.termux/files/usr/bin/python

import ast
import sys
from pathlib import Path

from dh import get_filez

DRY_RUN = not "-m" in sys.argv
cwd = Path.cwd()
err_dir = Path(f"{cwd}/error")
counter = 0


def process_file(path: Path) -> None:
    global counter
    path = Path(path)
    counter += 1
    print(f"{counter} {path.name}")
    content: str = ""
    try:
        content = path.read_text(encoding="utf-8")
    except:
        print(f"error reading {path}")
        return
    try:
        ast.parse(content)
        del content
        return
    except Exception as e:
        print(f"{path} | {e}")
        if not DRY_RUN:
            err_dir.mkdir(exist_ok=True)
            newpath = err_dir / path.name
            newpath = Path(newpath)
            newpath.write_text(content, encoding="utf-8")
            del content
            return
        else:
            print(f"{path.name} ast parse error")
            del content
            return


def main() -> None:
    for f in get_filez(cwd):
        if f.suffix == ".py":
            process_file(f)


if __name__ == "__main__":
    sys.exit(main())
