#!/data/data/com.termux/files/usr/bin/python


import sys
from pathlib import Path
from dh import STDLIB, get_ipkgs


def read_requirements(filename) -> list[str]:
    req_file = Path(filename)
    with Path(req_file).open(encoding="utf-8") as f:
        return [line.strip().replace("-", "_").lower() for line in f if line.strip() and not line.startswith("#")]


def strip_installed_from_requirements(fname: str) -> None:
    installed = get_ipkgs()
    installed = [p.lower().replace("-", "_") for p in installed if p]
    lines = read_requirements(fname)
    new_lines = [line for line in lines if line not in installed]
    new_lines = [line for line in new_lines if line not in STDLIB]
    Path(fname).write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    removed = len(lines) - len(new_lines)
    print(f"Removed {removed} packages")


if __name__ == "__main__":
    fn = sys.argv[1]
    strip_installed_from_requirements(fn)
