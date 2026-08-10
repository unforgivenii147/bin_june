#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

from os import scandir as os_scandir
from pathlib import Path

from dh import get_pyfiles, mpf3, runcmd

fixes = [
    "apply",
    "asserts",
    "basestring",
    "buffer",
    "dict",
    "except",
    "exec",
    "execfile",
    "exitfunc",
    "filter",
    "funcattrs",
    "future",
    "getcwdu",
    "has_key",
    "idioms",
    "import",
    "imports",
    "imports2",
    "input",
    "intern",
    "isinstance",
    "itertools",
    "itertools_imports",
    "long",
    "map",
    "metaclass",
    "methodattrs",
    "ne",
    "next",
    "nonzero",
    "numliterals",
    "operator",
    "paren",
    "print",
    "raise",
    "raw_input",
    "reduce",
    "renames",
    "repr",
    "set_literal",
    "standarderror",
    "sys_exc",
    "throw",
    "tuple_params",
    "types",
    "unicode",
    "urllib",
    "ws_comma",
    "xrange",
    "xreadlines",
    "zip",
]


def process_file(path: Path) -> None:
    path = Path(path)
    for fix in fixes:
        target_fix = f"--fix={fix}"
        cmd = ["2to3", "-w", target_fix, str(path)]
        runcmd(cmd, show_output=True)


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]

    files = [Path(p) for p in args] if args else get_pyfiles(cwd)

    mpf3(process_file, files)
