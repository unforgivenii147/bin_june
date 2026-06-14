#!/data/data/com.termux/files/usr/bin/python

import re
import sys
from pathlib import Path

from dh import cprint, fsz, get_files, gsz
from joblib import Parallel, delayed

CHUNK_SIZE = 1024 * 1024
N_JOBS = -1
multi_line_comment_re = "/\\*.*?\\*/"
single_line_comment_re = "//.*"


def process_file(fp) -> None:
    path = Path(path)
    print(f"processing ...{fp.name}")
    code = fp.read_text(encoding="utf-8")
    new_code = re.sub(multi_line_comment_re, "", code, flags=re.DOTALL)
    lines = new_code.splitlines()
    processed_lines = [re.sub(single_line_comment_re, "", line) for line in lines]
    final_code = "\n".join(processed_lines)
    final_code = re.sub("\\n\\s*\\n", "\\n\\n", final_code)
    final_code = "\n".join((line.rstrip() for line in final_code.splitlines()))
    fp.write_text(final_code, encoding="utf-8")


def main() -> None:
    cwd = Path.cwd()
    before = gsz(cwd)
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_files(p))
    else:
        files = get_files(
            cwd,
            e=[
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".jsm",
                ".h",
                ".java",
                ".c",
                ".cpp",
                ".hh",
                ".hpp",
                ".hxx",
                ".cc",
                ".cxx",
                ".mm",
            ],
        )
    Parallel(n_jobs=N_JOBS, backend="loky")((delayed(process_file)(f) for f in files))
    diffsize = before - gsz(cwd)
    cprint(f"space change : {fsz(diffsize)}", "cyan")


if __name__ == "__main__":
    sys.exit(main())
