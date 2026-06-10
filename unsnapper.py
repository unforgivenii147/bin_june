#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import cprint, decompress, fsz, get_files, gsz, mpf3


def process_file(path):
    path=Path(path)
    before = gsz(path)
    if not before:
        return
    data = path.read_bytes()
    decompressed = decompress(data)
    decomp_path = path.with_name(path.name.replace(".snappy", ""))
    decomp_path.write_bytes(decompressed)
    after = gsz(decomp_path)
    if not after:
        decomp_path.unlink()
        return
    diff_size = before - after
    ratio = diff_size / before * 100
    print(f"{decomp_path.name}", end=" | ")
    cprint(f"{fsz(before)} -> {fsz(after)} | {fsz(diff_size)} | {ratio:.1f}%")
    path.unlink()
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
