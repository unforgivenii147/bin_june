#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import compress, cprint, fsz, get_files, gsz, mpf3


def process_file(fp):
    before = gsz(fp)
    if not before:
        return
    data = fp.read_bytes()
    compressed = compress(data)
    snappy_path = fp.with_name(fp.name + ".snappy")
    snappy_path.write_bytes(compressed)
    after = gsz(snappy_path)
    if not after:
        snappy_path.unlink()
        return
    diff_size = before - after
    ratio = diff_size / before * 100
    print(f"{fp.name}", end=" | ")
    cprint(f"{fsz(before)} -> {fsz(after)} | {fsz(diff_size)} | {ratio:.1f}%")
    fp.unlink()
    return


def main():
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_files(p))
    else:
        files = get_files(cwd)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
