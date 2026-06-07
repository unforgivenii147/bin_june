#!/data/data/com.termux/files/usr/bin/python

import ast
from pathlib import Path
from sys import argv

from dh import run_command

if __name__ == "__main__":
    path = Path(argv[1])
    orig_code = path.read_text(encoding="utf-8")
    if path.suffix == ".rs":
        cmd = f"just-the-code -s {path!s}"
    elif path.suffix == ".py":
        cmd = f"just-the-code -s --language=python {path!s}"
    ret, new_code, err = run_command(cmd)
    if ret == 0 and len(orig_code) != len(new_code):
        if path.suffix == ".py":
            try:
                tree = ast.parse(new_code)
                path.write_text(new_code, encoding="utf-8")
            except:
                print("error")
        else:
            path.write_text(new_code, encoding="utf-8")
