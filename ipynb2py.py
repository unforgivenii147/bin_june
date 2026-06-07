#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

import nbformat

if __name__ == "__main__":
    fn = Path(sys.argv[1])
    with Path(fn).open(encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    fo = fn.with_suffix(".py")
    with Path(fo).open("w", encoding="utf-8") as out:
        for i, cell in enumerate(nb.cells, 1):
            out.write(f"#[{i}] ({cell.cell_type})\n")
            if cell.cell_type == "markdown":
                for line in cell.source.splitlines():
                    out.write(f"# {line}\n")
                    out.write("\n")
            elif cell.cell_type == "code":
                out.write(cell.source + "\n\n")
    print(f"Exported → {fo}")
