#!/data/data/com.termux/files/usr/bin/python
import ast
import sys
from pathlib import Path

from dh import cprint, get_pyfiles, mpf3

cwd = Path.cwd()
err_dir = cwd / "error"
counter = 0


def process_file(path: Path) -> None:
    global counter
    path = Path(path)
    counter += 1
    print(f"{counter} {path.name}")
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        return
    except Exception as e:
        print(f"{path} | {e}")
        err_dir.mkdir(exist_ok=True)
        newpath = err_dir / path.name
        path.rename(newpath)
            return
        else:
            print(f"{path.name} ast parse error")
            del content
            return


def main():
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []

    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_pyfiles(p))
    else:
        files = get_pyfiles(cwd)
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)

    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
