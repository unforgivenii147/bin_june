#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import sys
from pathlib import Path
from dh import get_files, mpf3, runcmd
CHUNK_SIZE = 1024 * 1024
def is_binary(path: Path | str) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum((1 for b in chunk if b not in text_chars))
        return nontext / len(chunk) > 0.3
    except Exception:
        return True
cwd = Path.cwd()
outfile = cwd / "all_strings.txt"
all_files = 0
c = 0
def process_file(path) -> None:
    path = Path(path)
    global all_files
    global c
    c += 1
    print(f"[{c}/{all_files}] {path.name}")
    if not path.exists() or not is_binary(path):
        return
    _, txt, _ = runcmd(["strings", str(path)], show_output=False)
    with outfile.open("a", encoding="utf-8") as f:
        f.write(f"\n# filename : {path.name}\n{txt}")
    return
def main() -> None:
    args = sys.argv[1:]
    global all_files
    files = [Path(arg) for arg in args] if args else get_files(cwd)
    all_files = len(files)
    mpf3(process_file, files)
if __name__ == "__main__":
    sys.exit(main())
