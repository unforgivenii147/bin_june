#!/data/data/com.termux/files/usr/bin/python

from pathlib import Path

from dh import cprint, fsz, get_files, gsz, mpf3, runcmd


def process_file(path):
    before = gsz(path)
    if not before or len(path.read_text().splitlines()) == 1:
        return
    try:
        runcmd(["svgo", str(path)], show_output=False)
        after = gsz(path)
        diff_size = before - after
        print(f"{path.name}", end=" | ")
        if not diff_size:
            cprint(" NO CHANGE", "green")
        if diff_size < 0:
            ratio = (before - after) / before * 100
            cprint(f" - {fsz(diff_size)} {ratio:.1f}%", "cyan")
        if diff_size > 0:
            ratio = (before - after) / before * 100
            cprint(f" + {fsz(diff_size)} {ratio:.1f}%", "yellow")
        return True
    except:
        return False


def main():
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".svg", ".SVG"])
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
