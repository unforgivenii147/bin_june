#!/data/data/com.termux/files/usr/bin/env python


import ast
import re
import sys
from multiprocessing import get_context
from pathlib import Path
from dh import fsz, get_nobinary, gsz, is_binary


def process_file(file_path: Path) -> None:
    path = Path(path)
    if is_binary(file_path):
        return
    before = gsz(file_path)
    file_path.read_text(encoding="utf-8")
    orig = re.sub(r"#.*", "")
    orig = re.sub(r"\n\n*", "\n")
    if file_path.suffix == ".py":
        try:
            ast.parse(orig)
            file_path.write_text(orig, encoding="utf-8")
            after = gsz(file_path)
            print(f"{file_path.name} ", end=" ")
            print(fsz(before - after))
        except:
            return
    else:
        file_path.write_text(orig, encoding="utf-8")
        after = gsz(file_path)
        print(f"{file_path.name} ", end=" ")
        print(fsz(before - after))


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = [Path(f) for f in args] if args else get_nobinary(cwd)
    p = get_context("spawn").Pool(8)
    for f in files:
        p.apply_async(process_file, (f,))
    p.close()
    p.join()
    diff_size = before - gsz(cwd)
    print(f"space change: {fsz(diff_size)}")


if __name__ == "__main__":
    main()
