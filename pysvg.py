#!/data/data/com.termux/files/usr/bin/python


from pathlib import Path
from dh import get_files, gsz, mpf3, rrs, runcmd


def process_file(path) -> None:
    path = Path(path)
    if "lazy" in path.parts:
        return
    before = gsz(path)
    if not before or len(path.read_text().splitlines()) == 1:
        return
    try:
        runcmd(["svgo", str(path)], show_output=False)
        after = gsz(path)
        rrs(path, before, after)
        return
    except:
        return


def main() -> None:
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".svg", ".SVG"])
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
