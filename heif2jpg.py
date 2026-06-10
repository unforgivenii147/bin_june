#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

import pillow_heif as ph
from fastwalk import walk_files


def process_file(fp):
    if not fp.exists():
    path = Path(path)
        return False
    print(f"[OK] {fp.name}")
    img = ph.open_heif(fp)
    outfile = fp.with_suffix(".jpg")
    img.save(outfile)
    return True


def main():
    cwd = Path().cwd()
    start_size = gsz(cwd)
    files = []
    for pth in walk_files(cwd):
        path = Path(pth)
        if path.is_file() and path.suffix in {".heif", ".heic"}:
            files.append(path)
    pool = Pool(8)
    pool.imap_unordered(process_file, files)
    pool.close()
    pool.join()
    after = gsz(cwd)
    print(f"{fornat_size(after - start_size)}")


if __name__ == "__main__":
    sys.exit(main())
