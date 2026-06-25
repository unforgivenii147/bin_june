#!/data/data/com.termux/files/usr/bin/python

import shutil
import sys
from pathlib import Path

from dh import get_filez, read_lines

EMPTYIT = "-e" in sys.argv
RMIT = "-r" in sys.argv
junk_path = Path("/sdcard/data/junk")
SKIP_DIRS = ["lazy", ".git"]


def empty_it(path: Path) -> None:
    path.write_text("", encoding="utf-8")


def remove_it(fp: Path) -> None:
    if fp.exists():
        if fp.is_dir():
            shutil.rmtree(fp)
        else:
            fp.unlink()


def load_junk() -> list[str]:
    return read_lines(junk_path)


def main() -> None:
    cwd = Path.cwd()
    junk_files = load_junk()
    junkset = set(junk_files)
    c = 0
    for path in get_filez(cwd):
        if ".git" in path.parts or "lazy" in path.parts or "var" in path.parts:
            continue
        loname = path.name.lower()
        if loname in junkset:
            path.unlink()
            print(f"{path.name} removed.")
            continue
        if loname == "copying":
            path.unlink()
            print(f"{path.name} removed.")
            continue
        if loname.endswith((".tmp", ".bak", ".log")):
            remove_it(path)
            print(path.relative_to(cwd))
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
            print(path.relative_to(cwd))
            c += 1
            continue
        if loname.endswith("license.txt") or loname == "license":
            path.unlink()
            c += 1
            print(path.relative_to(cwd))
            continue
        if any((loname == junk for junk in junk_files)):
            if RMIT:
                path.unlink()
                print(path.relative_to(cwd))
                c += 1
                continue
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
