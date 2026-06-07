#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import cprint, fsz, gsz, runcmd


def safe_run(path):
    cmd = ["terser", "--compress", "--mangle", "--", str(path)]
    res, txt, err = runcmd(cmd, show_output=False)
    if res != 0:
        print(f"Error running terser: {err}", file=sys.stderr)
        return False
    path.write_text(txt, encoding="utf8")
    return True


def process_file(fp) -> bool:
    if "site-packages" in fp.parts and "notebook" in fp.parts:
        return False
    before = gsz(fp)
    if not fp.exists() or not before:
        return False
    if len(fp.read_text().splitlines()) == 1:
        return False
    print(f"{fp.name}", end=" ")
    res = safe_run(fp)
    if res:
        after = gsz(fp)
        diffsize = before - after
        if not diffsize:
            cprint("[NO CHANGE]", "white")
        if diffsize:
            ratio = diffsize / before * 100
            cprint(f"[OK] + {fsz(diffsize)} {abs(ratio):.1f}%", "cyan")
        return True
    cprint("[ERROR]", "red")
    return False


def main():
    from dh import get_files, mpf3

    args = sys.argv[1:]
    cwd = Path.cwd()
    before = gsz(cwd)
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".js", ".cjs", ".mjs", ".jsx", ".tsx"])
    _ = mpf3(process_file, files)
    diff_size = before - gsz(cwd)
    cprint(f"space freed : {fsz(diff_size)}", "green")


if __name__ == "__main__":
    sys.exit(main())
