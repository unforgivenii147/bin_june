#!/data/data/com.termux/files/usr/bin/python

from pathlib import Path

from dh import cprint, get_files, mpf3, unique_path
from fontTools.ttLib import woff2

cwd = Path.cwd()


def process_file(path: Path):
    path = Path(path)
    woff2_path = path.with_suffix(".woff2")
    if woff2_path.exists() and woff2_path.stat().st_size:
        woff2_path = unique_path(woff2_path)
    try:
        woff2.compress(path, woff2_path)
        print(f"{path.name} converted.")
        path.unlink()
    except:
        cprint(f"error convering {path.name}")


def main():
    files = get_files(cwd, ext=[".ttf", ".otf"])
    _ = mpf3(process_file, files)


if __name__ == "__main__":
    main()
