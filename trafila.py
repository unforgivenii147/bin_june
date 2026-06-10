#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

import trafilatura
from dh import get_files, mpf3


def process_file(html_file: Path):
    path = Path(path)
    try:
        html_content = html_file.read_text(encoding="utf-8")
        markdown = trafilatura.extract(
            html_content,
            output_format="markdown",
            include_links=True,
            include_images=True,
            include_tables=True,
            no_fallback=False,
        )
        if markdown:
            md_file = html_file.with_suffix(".md")
            md_file.write_text(markdown, encoding="utf-8")
            print(f"✓ Converted: {html_file.name} -> {md_file.name}")
            return (md_file, True)
        print(f"✗ No content extracted from {html_file.name}")
        return (html_file, False)
    except Exception as e:
        print(f"✗ Error: {e}")
        return (html_file, False)


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".html", ".htm", ".xhtml", ".xhtm"])
    numf = len(files)
    if numf == 1:
        process_file(files[0])
        sys.exit(0)
    mpf3(process_file, files)
