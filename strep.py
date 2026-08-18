#!/data/data/com.termux/files/home/.local/bin/python
"""Strip debug symbols from .so files, including those inside .whl archives."""

import re
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile
from dh import cprint, fsz, gsz, mpf3, runcmd

SO_PATTERN = re.compile(r"\.so(\.\d+)*$")


def process_file(path: Path) -> None:
    path = Path(path)
    before = path.stat().st_size
    _ret, _, _ = runcmd(["strip", str(path)], show_output=True)
    after = path.stat().st_size
    if not after:
        return
    dz = before - after
    if dz:
        cprint(f"{path.name} | ratio: {after / before:.1f}%")


def process_whl(whl_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        with ZipFile(whl_path, "r") as zf:
            zf.extractall(tmpdir)
        so_files = [p for p in tmpdir.rglob("*") if SO_PATTERN.search(p.name)]
        for so_file in so_files:
            process_file(so_file)
        with ZipFile(whl_path, "w") as zf:
            for file_path in tmpdir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(tmpdir))


def collect_files(cwd: Path, args: list[str]) -> list[Path]:
    if args:
        return [Path(p) for p in args]
    so_files = [p for p in cwd.rglob("*") if SO_PATTERN.search(p.name) and p.is_file()]
    whl_files = list(cwd.rglob("*.whl"))
    return so_files + whl_files


if __name__ == "__main__":
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = collect_files(cwd, args)
    so_files = [f for f in files if f.suffix in (".so",) or SO_PATTERN.search(f.name)]
    whl_files = [f for f in files if f.suffix == ".whl"]
    mpf3(process_file, so_files)
    for whl in whl_files:
        process_whl(whl)
    after = gsz(cwd)
    dsz = before - after
    if dsz:
        print(f"space freed: {fsz(dsz)}")
