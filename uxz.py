#!/data/data/com.termux/files/usr/bin/env python
import sys
import tarfile
from collections import deque
from pathlib import Path

from lzma_mt import LZMADecompressor


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


MEM_LIMIT = 104857600


def decompress_file(path: Path) -> bool:
    fname = path.name
    if fname.endswith(".tar.xz"):
        extract_path = path.parent / f"{fname.replace('.tar.xz', '')}"
        with tarfile.open(path, "r:xz") as tar:
            tar.extractall(path=extract_path, filter="data")
        return True
    elif fname.endswith(".xz"):
        compressed_data = path.read_bytes()
        out_path = path.parent / f"{fname.replace('.xz', '')}"
        decompressor = LZMADecompressor(memlimit=MEM_LIMIT, threads=4)
        decompressed_data = decompressor.decompress(compressed_data)
        with out_path.open("wb") as f:
            f.write(decompressed_data)
        return True
    return False


def main() -> None:
    sys.argv[1:]
    successful = 0
    errors = 0
    start_dir = Path.cwd()
    files = get_files(start_dir, ext=[".xz", ".tar.xz"])
    if not files:
        print("No files to decompress")
        return
    for i, path in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Processing...")
        real_path = path
        if "/storage/emulated/0" in str(path):
            path_str = str(path).replace("/storage/emulated/0", "/sdcard")
            real_path = Path(path_str)
        if decompress_file(real_path):
            successful += 1
            real_path.unlink()
        else:
            errors += 1
    print(f"successfull: {successful}\nerrors: {errors}")


if __name__ == "__main__":
    main()
