#!/data/data/com.termux/files/usr/bin/python
import sys
from pathlib import Path
from dh import runcmd, get_pyfiles


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


def process_file(fp):
    for fix in fixes:
        target_fix = f"--fix={fix}"
        cmd = ["2to3-2.7", "-w", target_fix, str(fp)]
        runcmd(cmd, show_output=True)


if __name__ == "__main__":
    cwd = Path.cwd()
    files = get_pyfiles(cwd)
    for f in files:
        process_file(f)
