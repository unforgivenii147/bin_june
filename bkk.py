#!/data/data/com.termux/files/usr/bin/python
import sys
from pathlib import Path
from dh import get_files,mpf3

def process_file(path):
    path=Path(path)
    if not path.exists():
        return
    if path.name.endswith((".bak",".log")):
        print(path.name)
        path.unlink()
    return

if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd)
    mpf3(process_file,files)
