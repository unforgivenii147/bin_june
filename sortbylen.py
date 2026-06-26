#!/data/data/com.termux/files/usr/bin/python
import sys
from pathlib import Path
from dh import read_lines


def sort_by_length(lines: list[str]) -> list[str]:
    return sorted(lines, key=len)


if __name__ == "__main__":

    path = Path(sys.argv[1].strip())
    lines = read_lines(path, ke=True)
    sorted_lines = sort_by_length(lines)
    path.write_text("".join(sorted_lines), encoding="utf8")
    print(f"{path.name} updated")
