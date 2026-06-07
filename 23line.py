#!/data/data/com.termux/files/usr/bin/python

from __future__ import annotations

import os
from pathlib import Path

from dh import gext

EXT = [".py", ".h", ".c", ".cpp", ".cc", ".cxx", ".hh", ".hpp", ".h", ".hxx"]


def get_first_13(path: str) -> str:
    with Path(path).open(encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return "".join(lines[:13])


def main() -> None:
    output_path = "all.txt"
    collected = []
    for base, _, files in os.walk(Path.cwd()):
        for name in files:
            ext = gext(name)
            if ext not in EXT:
                continue
            path = os.path.join(base, name)
            if Path(path).resolve() == Path(output_path).resolve():
                continue
            snippet = get_first_13(path)
            collected.append(snippet)
    unique_collected = list(set(collected))
    with Path(output_path).open("w", encoding="utf-8") as out:
        for snippet in unique_collected:
            out.write(snippet)
            out.write("\n\n\n")
    print(f"Unique snippets saved → {output_path}")
    print(f"Total unique blocks: {len(unique_collected)}")


if __name__ == "__main__":
    main()
