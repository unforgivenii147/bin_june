#!/data/data/com.termux/files/usr/bin/python

import os
import shutil
import sys
from pathlib import Path
from dh import cprint

major, minor, _, _, _ = sys.version_info
py_version = f"{major}.{minor}"


def process_dir(dr: Path) -> bool:
    print(dr.name)
    if "dist-info" in str(dr.name):
        for k in os.listdir(dr):
            if k in {"top_level.txt", "entry_points.txt"}:
                cprint(f"{dr} removed", "cyan")
                shutil.rmtree(dr)
    return True


def main() -> None:
    cwd = f"/data/data/com.termux/files/usr/lib/python{py_version}/site-packages"
    for pth in os.listdir(cwd):
        path = Path(os.path.join(cwd, pth))
        if path.is_dir() and len(os.listdir(path)) == 1:
            process_dir(path)


if __name__ == "__main__":
    sys.exit(main())
