#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import partial_ratio
from pip._internal.cli.main import main as pip_main

WHL_DIR = Path("/sdcard/whl")
WILDCARD = "-w" in sys.argv


def install(packages: list[str]):
    args = ["install", "--no-compile", "--no-deps", *packages]
    return pip_main(args)


def pkg_name(txt):
    indx = txt.index("-")
    slash = txt.rfind("/")
    return txt[slash + 1 : indx]


def install_by_wildcard(pkg):
    whl = {pkg_name(str(p)): str(p) for p in WHL_DIR.glob("*.whl")}
    wheel_files = []
    for k, v in whl.items():
        pr = partial_ratio(pkg, k)
        if pkg in k and pr == 100:
            wheel_files.append(v)
    if not wheel_files:
        print(f"No .whl files found matching '{pkg}*'")
        return
    try:
        res = install(wheel_files)
        if not res:
            for f in wheel_files:
                print(f"  - {Path(f).name}")
                Path(f).unlink()
    except:
        return


def install_whl(pkg):
    whl = {pkg_name(str(p)): str(p) for p in WHL_DIR.glob("*.whl")}
    wheel_files = []
    for k, v in whl.items():
        if pkg in k:
            wheel_files.append(v)
    if not wheel_files:
        print(f"No .whl files found matching '{pkg}*'")
        return
    try:
        res = install(wheel_files)
        if not res:
            for f in wheel_files:
                print(f"  - {Path(f).name}")
                Path(f).unlink()
    except:
        return


if __name__ == "__main__":
    args = sys.argv[1:]
    candidates = [p.strip() for p in args if p.strip() != "-w"] if args else None
    if candidates is not None:
        for pkg in candidates:
            if WILDCARD:
                install_by_wildcard(pkg)
            else:
                install_whl(pkg)
