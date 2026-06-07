#!/data/data/com.termux/files/usr/bin/python

import sys
import tarfile
import zipfile
from pathlib import Path

from dh import get_files, unique_path


def whl_to_tar_xz(whl_path: Path):
    target = whl_path.with_suffix(".tar.xz")
    if target.exists():
        target = unique_path(target)
    try:
        with zipfile.ZipFile(whl_path, "r") as zf, tarfile.open(target, "w:xz") as tf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                with zf.open(member) as source:
                    tarinfo = tarfile.TarInfo(name=member.filename)
                    tf.addfile(tarinfo, source)
        print(f"[OK] Created {target.name}")
        whl_path.unlink()
    except Exception as e:
        print(f"[ERROR] {whl_path.name}: {e}")


def main():
    args = sys.argv[1:]
    cwd = Path().cwd()
    files = [Path(arg) for arg in args] if args else get_files(cwd, recursive=False, ext=[".whl"])
    if len(files) == 1:
        whl_to_tar_xz(files[0])
        sys.exit(0)
    for f in files:
        whl_to_tar_xz(f)


if __name__ == "__main__":
    sys.exit(main())
