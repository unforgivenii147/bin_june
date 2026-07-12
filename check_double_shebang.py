#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path


from pathlib import Path
from os import scandir as os_scandir


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def process_file(path: Path) -> None:
    path = Path(path)
    if path.is_symlink():
        return
    content = path.read_text()
    lines = content.splitlines()
    c = 0
    for line in lines:
        if line.startswith("#!"):
            c += 1
    if c > 1:
        print(path.name)


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            if p.is_dir():
                files.extend(get_files(p))
    else:
        files = get_files(cwd, ext=[".py"])
    for f in files:
        process_file(f)


if __name__ == "__main__":
    sys.exit(main())
