#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path
from dh import cprint, get_files, mpf3, runcmd


def safe_run(path) -> bool:
    path = Path(path)
    cmd = ["mandoc", "-T", "html", str(path)]
    res, txt, err = runcmd(cmd, show_output=False)
    if res != 0:
        print(f"Error running terser: {err}", file=sys.stderr)
        return False
    outpath = path.with_suffix(".html")
    outpath.write_text(txt, encoding="utf8")
    path.unlink()
    return True


def process_file(path) -> bool:
    path = Path(path)
    if not path.exists():
        return False
    print(f"{path.name}", end=" ")
    res = safe_run(path)
    if res:
        cprint(f"[✓] ", "cyan")
        return True
    cprint("[ERROR]", "red")
    return False


def main() -> None:
    args = sys.argv[1:]
    cwd = Path.cwd()
    files = (
        [Path(p) for p in args]
        if args
        else get_files(
            cwd, ext=[".1", ".3", ".3am", ".3form", ".3menu", ".3ncurses", ".3readline", ".3t", ".4", ".5", ".7", ".8"]
        )
    )
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
