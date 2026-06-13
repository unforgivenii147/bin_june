#!/data/data/com.termux/files/usr/bin/python

import mmap
import sys
from pathlib import Path

import brotlicffi
from dh import cprint, fsz, get_files, gsz
from joblib import Parallel, delayed

CHUNK_SIZE = 32 * 1024 * 1024
QUALITY = 5
N_JOBS = -1


def compress_chunk(data, quality=QUALITY):
    return brotlicffi.compress(data, quality=quality)


def parallel_compress(in_path, out_path):
    file_size = in_path.stat().st_size
    chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    with out_path.open("wb", buffering=1024 * 1024) as fout, in_path.open("rb") as fin:
        mm = mmap.mmap(fin.fileno(), length=0, access=mmap.ACCESS_READ)
        chunks = [mm[i * CHUNK_SIZE : min((i + 1) * CHUNK_SIZE, file_size)] for i in range(chunk_count)]
        compressed_chunks = Parallel(n_jobs=N_JOBS, backend="loky")(
            (delayed(compress_chunk)(chunk) for chunk in chunks)
        )
        for block in compressed_chunks:
            fout.write(len(block).to_bytes(4, "big"))
            fout.write(block)
        mm.close()


def process_file(path):
    path = Path(path)
    if not path.exists() or path.suffix == ".br":
        return
    before = gsz(path)
    outfile = Path(str(path) + ".br")
    parallel_compress(path, outfile)
    path.unlink()
    after = gsz(outfile)
    ratio = round((before - after) / before * 100, 3)
    cprint(f"{outfile.name}", "green", end=" | ")
    cprint(f"{ratio}", "cyan")
    del before, after, ratio
    return


def main():
    root_dir = Path.cwd()
    before = gsz(root_dir)
    args = sys.argv[1:]
    files = [Path(arg) for arg in args] if args else get_files(root_dir)
    for f in files:
        process_file(f)
    diff_size = before - gsz(root_dir)
    print(f"{fsz(diff_size)}")


if __name__ == "__main__":
    sys.exit(main())
