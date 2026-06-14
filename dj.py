#!/data/data/com.termux/files/usr/bin/python

import shutil
import sys
from pathlib import Path

from dh import get_filez, read_lines

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
    c = 0
    for path in get_filez(cwd):
        if ".git" in path.parts or "nvim" in path.parts or "var" in path.parts:
            continue
        loname = path.name.lower()
        if loname.endswith((".tmp", ".bak", ".log")):
            remove_it(path)
            print(path.name)
            c += 1
            continue
        if loname in {
            ".travis.yml",
            "third_party_notices",
            ".gitkeep",
            ".dirinfo",
            ".pyformat_cache.json",
            "simz.json",
            "copyright",
        }:
            path.unlink()
            print(path.name)
            c += 1
            continue
        if (
            loname.endswith("license.txt")
            or (path.stem.lower() == "license" and (not path.suffix in {".c", ".py", ".pyx", ".js", ".pxd"}))
            or any((loname == junk for junk in junk_files))
        ) and path.exists():
            if RMIT:
                remove_it(path)
                print(path.relative_to(cwd))
                c += 1
                continue
            elif EMPTYIT:
                empty_it(path)
                print(path.relative_to(cwd))
                c += 1
            else:
                empty_it(path)
                print(path.relative_to(cwd))
                c += 1
        if path.is_dir() and path.name == "licenses" and ("dist-info" in path.parent.name):
            remove_it(path)
            print(path.relative_to(cwd))
            c += 1
    if c:
        print(f"{c} item removed")


if __name__ == "__main__":
    sys.exit(main())
