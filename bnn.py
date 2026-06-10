#!/data/data/com.termux/files/usr/bin/python


def process_file(fname):
    content = fname.read_text(encoding="utf-8")
    path = Path(path)
    content = content.replace("\\n", "\n")
    fname.write_text(content, encoding="utf-8")
    print(f"{fname.name} updated.")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from dh import get_pyfiles, mpf3

    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_pyfiles(cwd)
    mpf3(process_file, files)
