#!/data/data/com.termux/files/usr/bin/python

from pathlib import Path

from dh import cprint, fsz, get_files, gsz, mpf3, runcmd, rrs


def process_file(path) -> bool | None:
    path = Path(path)
    before = gsz(path)
    if not before or len(path.read_text().splitlines()) == 1:
        return
    try:
        runcmd(["svgo", str(path)], show_output=False)
        after = gsz(path)
        rrs(path, before, after)
        return True
    except:
        return False


def main() -> None:
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".svg", ".SVG"])
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
