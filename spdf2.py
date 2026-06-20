#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import runcmd


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} TB"


def process_file(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        print("Input file not found.", file=sys.stderr)
        sys.exit(1)
    temp_qpdf = path.with_name(f"temp_qpdf_{path.name}")
    before = path.stat().st_size
    print(f"Before : {human_size(before)}")
    qpdf_cmd = ["qpdf", "--linearize", "--object-streams=generate", str(path), str(temp_qpdf)]
    runcmd(qpdf_cmd, show_output=True)
    if temp_qpdf.exists():
        after = temp_qpdf.stat().st_size
        print(f"After  : {human_size(after)}")
        diff = before - after
        sign = "-" if diff >= 0 else "+"
        if after < before:
            temp_qpdf.replace(path)
            print(f"Saved  : {sign}{human_size(abs(diff))}")
        else:
            print("original file is smaller")
            temp_qpdf.unlink(missing_ok=True)


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    if args:
        files = [Path(p) for p in args]
        for path in files:
            process_file(path)
        sys.exit(0)
    for path in cwd.rglob("*.pdf"):
        process_file(path)


if __name__ == "__main__":
    main()
