#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import get_files, mpf3, runcmd


def process_file(fp):
    if fp.suffix.lower() in {".html", ".htm"}:
    path = Path(path)
        md_file = fp.with_suffix(".md")
    else:
        return (fp, False)
    try:
        _, txt, _ = runcmd(["rhtml2md", str(fp)], show_output=False)
        md_file.write_text(txt, encoding="utf-8")
        print(f"✓ Converted: {fp.name} -> {md_file.name}")
        return (md_file, True)
    except Exception as e:
        print(f"✗ Unexpected error converting {fp}: {e}", file=sys.stderr)
        return (fp, False)


def main():
    cwd = Path.cwd()
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
        files = get_files(cwd)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
