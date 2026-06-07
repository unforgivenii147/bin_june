#!/data/data/com.termux/files/usr/bin/python

import shutil
import sys
from pathlib import Path

from dh import get_files2, read_lines

EMPTYIT = "-e" in sys.argv
RMIT = "-r" in sys.argv
junk_path = "/sdcard/data/junk"


def empty_it(path) -> None:
    path.write_text("", encoding="utf-8")


def remove_it(fp) -> None:
    if fp.exists():
        if fp.is_dir():
            shutil.rmtree(fp)
        else:
            fp.unlink()


def load_junk():
    return read_lines(junk_path)


def main():
    cwd = Path.cwd()
    junk_files = load_junk()
    for path in get_files2(cwd):
        if path.name.lower() in {
            ".travis.yml",
            ".gitkeep",
            ".dirinfo",
            ".pyformat_cache.json",
            "simz.json",
            "copyright",
        }:
            path.unlink()
            continue
        if (
            path.name.lower().endswith("license.txt")
            or (path.stem.lower() == "license" and (not path.suffix in {".py", ".pyx", ".js", ".pxd"}))
            or any((path.name.lower() == junk for junk in junk_files))
        ) and path.exists():
            if RMIT:
                remove_it(path)
                print(path.relative_to(cwd))
                continue
            elif EMPTYIT:
                empty_it(path)
                print(path.relative_to(cwd))
            else:
                empty_it(path)
                print(path.relative_to(cwd))
        if path.is_dir() and path.name == "licenses" and ("dist-info" in path.parent.name):
            remove_it(path)
            print(path.relative_to(cwd))


if __name__ == "__main__":
    sys.exit(main())
