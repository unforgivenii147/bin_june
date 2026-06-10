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


def process_file(input_path):
    path = Path(path)
    if not input_path.exists():
        print("Input file not found.", file=sys.stderr)
        sys.exit(1)
    temp_qpdf = input_path.with_name(f"temp_qpdf_{input_path.name}")
    size_before = input_path.stat().st_size
    print(f"Before : {human_size(size_before)}")
    qpdf_cmd = ["qpdf", "--linearize", "--object-streams=generate", str(input_path), str(temp_qpdf)]
    runcmd(qpdf_cmd, show_output=True)
    if temp_qpdf.exists():
        size_after = temp_qpdf.stat().st_size
        print(f"After  : {human_size(size_after)}")
        diff = size_before - size_after
        sign = "-" if diff >= 0 else "+"
        if size_after < size_before:
            temp_qpdf.replace(input_path)
            print(f"Saved  : {sign}{human_size(abs(diff))}")
        else:
            print("original file is smaller")
            temp_qpdf.unlink(missing_ok=True)


def main():
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
