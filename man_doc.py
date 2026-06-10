#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import cprint, get_files, mpf3, runcmd


def safe_run(path):
    cmd = ["mandoc", "-T", "html", str(path)]
    res, txt, err = runcmd(cmd, show_output=False)
    if res != 0:
        print(f"Error running terser: {err}", file=sys.stderr)
        return False
    outpath = path.with_suffix(".html")
    outpath.write_text(txt, encoding="utf8")
    return True


def process_file(fp) -> bool:
    path = Path(path)
    if not fp.exists():
        return False
    print(f"{fp.name}", end=" ")
    res = safe_run(fp)
    if res:
        cprint(f"[✓] ", "cyan")
        return True
    cprint("[ERROR]", "red")
    return False


def main():
    args = sys.argv[1:]
    cwd = Path.cwd()
    files = (
        [Path(p) for p in args]
        if args
        else get_files(cwd, ext=[".1", ".2", ".3", ".4", ".5", ".6", ".7", ".8", ".9", ".n", ".gz"])
    )
    _ = mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
