#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import get_files, runcmd


def process_file(fp) -> bool:
    try:
        out = fp.with_suffix(".ttf")
        cmd = ["fontforge", "-lang=ff", "-c", '"Open($1); Generate($2);"', str(fp), str(out)]
        ret, _, _ = runcmd(cmd, show_output=False)
        if not ret:
            print(f"✓ {fp.name}")
            return True
        print(f"✘ {fp.name}")
        return False
    except:
        print(f"error processing {fp.name}")
        return False


def main():
    cwd = Path.cwd()
    args = sys.argv[1:]
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            if p.is_dir():
                files.extend(get_files(p))
    else:
        files = get_files(cwd)
    for f in files:
        if f.suffix != ".ttf":
            process_file(f)


if __name__ == "__main__":
    sys.exit(main())
