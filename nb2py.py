#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

import nbformat

INPUT = Path(sys.argv[1])
OUTPUT = Path(INPUT).with_suffix(".py")
nb = nbformat.read(INPUT, as_version=4)
with Path(OUTPUT).open("w", encoding="utf-8") as out:
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            out.write('"""\n')
            out.write(cell.source + "\n")
            out.write('"""\n\n')
        elif cell.cell_type == "code":
            out.write(cell.source + "\n\n")
print(f"Exported → {OUTPUT}")
