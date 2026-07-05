#!/data/data/com.termux/files/usr/bin/python


import sys
from pathlib import Path
from dh import compress, cprint, decompress, fsz, get_files, gsz, mpf3

COMPRESS = "-c" in sys.argv
DECOMPRESS = "-d" in sys.argv
MODE = "COMPRESS"


def compress_file(path: Path) -> None:
    before = gsz(path)
    if not before:
        return
    data = path.read_bytes()
    compressed = compress(data)
    snappy_path = path.with_name(path.name + ".snappy")
    snappy_path.write_bytes(compressed)
    after = gsz(snappy_path)
    if not after:
        snappy_path.unlink()
        return
    diff_size = before - after
    ratio = diff_size / before * 100
    print(f"{path.name}", end=" | ")
    cprint(f"{fsz(before)} -> {fsz(after)} | {fsz(diff_size)} | {ratio:.1f}%")
    path.unlink()
    return


def decompress_file(path: Path) -> None:
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
    ratio = before / after * 100
    print(f"{decomp_path.name}", end=" | ")
    cprint(f"{fsz(before)} -> {fsz(after)} | {fsz(diff_size)} | {ratio:.1f}%")
    path.unlink()
    return


def process_file(path) -> None:
    path = Path(path)
    if MODE == "COMPRESS":
        compress_file(path)
    elif MODE == "DECOMPRESS":
        decompress_file(path)


def main() -> None:
    global mode
    if COMPRESS:
        mode = "COMPRESS"
    if DECOMPRESS:
        mode = "DECONPRESS"
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
