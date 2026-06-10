#!/data/data/com.termux/files/usr/bin/python

from pathlib import Path

import htmlmin
from dh import mpf3


def process_file(file: Path) -> bool:
    path = Path(path)
    try:
        orig = file.read_text(encoding="utf-8")
        print(len(orig))
        code = orig
        code = htmlmin.minify(orig, remove_comments=True)
        print(len(code))
        if len(code) != len(orig):
            Path(file).write_text(code, encoding="utf-8")
            print(f"[OK] {file.name}")
            return True
    except Exception:
        print(f"[ERR] {file.name}")
        return False


def main() -> None:
    files = []
    cwd = Path.cwd()
    for path in cwd.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".htm"}:
            files.append(path)
    if not files:
        print("No html files detected.")
        return
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
