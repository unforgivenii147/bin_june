#!/data/data/com.termux/files/usr/bin/python


import re
import sys
from pathlib import Path
from dh import get_files, mpf3


def process_file(path) -> None:
    path = Path(path)
    ansi_re = re.compile(b"\\x1b\\[[?]?[0-9;]*[a-zA-Z]")
    osc_re = re.compile(b"\\x1b\\][^\\x07\\x1b]*[\\x07\\x1b]")
    misc_escape_re = re.compile(b"\\x1b[PX^_][^\\x1b]*\\x1b\\\\|\\x1b[@-_]")
    cr_re = re.compile(b"\\r\\n?|\\n\\r?")
    charset_re = re.compile(b"\\x1b[()][0-9a-zA-Z]")
    try:
        content = path.read_bytes()
        content = charset_re.sub(b"", content)
        content = osc_re.sub(b"", content)
        content = misc_escape_re.sub(b"", content)
        content = ansi_re.sub(b"", content)
        content = cr_re.sub(b"\n", content)
        text = content.decode("utf-8", errors="replace")
        cleaned_lines = []
        for line in text.splitlines(keepends=True):
            cleaned_line = re.sub("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]", "", line)
            cleaned_lines.append(cleaned_line)
        result = "".join(cleaned_lines)
        path.write_text(result, encoding="utf-8")
        print(f"✓  {path.name}")
    except Exception as e:
        print(f"✗ Error processing {path.name}: {e}", file=sys.stderr)
        return


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".log", ".txt", ".md"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
