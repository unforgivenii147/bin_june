#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path
from dh import runcmd, mpf_async, get_files, fsz


def process_file(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        print("Input file not found.", file=sys.stderr)
        sys.exit(1)
    temp_qpdf = path.with_name(f"temp_qpdf_{path.name}")
    before = path.stat().st_size
    print(f"{path.name} Before : {fsz(before)}")
    qpdf_cmd = ["qpdf", "--linearize", "--object-streams=generate", str(path), str(temp_qpdf)]
    runcmd(qpdf_cmd, show_output=True)
    if temp_qpdf.exists():
        after = temp_qpdf.stat().st_size
        print(f"{path.name} After  : {fsz(after)}")
        diff = before - after
        sign = "-" if diff >= 0 else "+"
        if after < before:
            temp_qpdf.replace(path)
            print(f"Saved  : {sign}{fsz(abs(diff))}")
        else:
            print("original file is smaller")
            temp_qpdf.unlink(missing_ok=True)


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".pdf"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    mpf_async(process_file, files)


if __name__ == "__main__":
    main()
