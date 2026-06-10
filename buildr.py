#!/data/data/com.termux/files/usr/bin/python

import os
from pathlib import Path

from dh import runcmd, get_files, mpf3


def process_file(fp):
    path = Path(fp)
    path = Path(path)
    pardir = str(path.parent)
    os.system(f"cd {pardir}")
    os.chdir(str(pardir))
    cmd = ["python", "setup.py", "bdist_wheel"]
    ret, _, _ = runcmd(cmd)
    if ret != 0:
        print("ok")


if __name__ == "__main__":
    cwd = Path.cwd()
    files = get_files(cwd)
    targets = []
    for path in files:
        if path.name == "setup.py":
            targets.append(str(path))
    mpf3(process_file, targets)
    whl_files = get_files(cwd, ext=[".py"])
    if whl_files:
        for k in whl_files:
            print(k)
