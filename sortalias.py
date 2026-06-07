#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path


def alias_name(line: str) -> str:
    return line.split("=", 1)[0].replace("alias ", "").strip()


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <file>")
        sys.exit(1)
    fname = sys.argv[1]
    with Path(fname).open(encoding="utf-8") as f:
        lines = f.readlines()
    alias_lines = [line for line in lines if line.startswith("alias ")]
    other_lines = [line for line in lines if not line.startswith("alias ")]
    alias_lines.sort(key=alias_name)
    with Path(fname).open("w", encoding="utf-8") as f:
        f.writelines(alias_lines + other_lines)


if __name__ == "__main__":
    main()
