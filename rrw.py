#!/data/data/com.termux/files/usr/bin/python

import ast
import sys
import unicodedata
from pathlib import Path

import astor
from dh import get_files, is_binary

BACKUP = False


def process_file(fn: Path) -> None:
    path = Path(path)
    if is_binary(fn):
        return
    try:
        content = fn.read_text(encoding="utf-8", errors="ignore")
        if BACKUP:
            backup_file = fn.with_suffix(fn.suffix + ".bak")
            backup_file.write_text(content, encoding="utf-8")
        new_content = content
        if fn.suffix == ".py":
            try:
                tree = ast.parse(content)
                new_content = astor.to_source(tree)
                fn.write_text(new_content, encoding="utf-8")
                print(f"\x1b[0m[ \x1b[6;96m✓\x1b[0m ] {fn.name} ")
                return
            except:
                print(f"\x1b[0m[ \x1b[6;96m✘\x1b[0m ] {fn.name} ")
                return
        else:
            new_content = unicodedata.normalize("NFD", content)
            fn.write_text(new_content, encoding="utf-8")
    except:
        return


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    backup = sys.argv[2] if len(sys.argv) > 2 else False
    files = [Path(arg) for arg in args] if args else get_files(cwd)
    for path in files:
        process_file(path)


if __name__ == "__main__":
    raise SystemExit(main())
