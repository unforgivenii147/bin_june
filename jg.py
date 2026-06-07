#!/data/data/com.termux/files/usr/bin/python

import shutil
from pathlib import Path


def process_dir(pardir):
    dotgit = pardir / ".git"
    if not dotgit.exists():
        return False
    for path in pardir.glob("*"):
        if path.is_dir() and path.name != ".git":
            shutil.rmtree(str(path))
        if path.is_file():
            path.unlink()
    return True


def find_targets(root_dir: Path):
    for dpath in root_dir.rglob("*"):
        if dpath.is_dir() and dpath.name == ".git":
            parent_of_dotgit = dpath.parent
            process_dir(parent_of_dotgit)


if __name__ == "__main__":
    cwd = Path.cwd()
    find_targets(cwd)
    for p in cwd.glob("*"):
        print(p.relative_to(cwd))
