#!/data/data/com.termux/files/usr/bin/python

import re
import sys
from pathlib import Path

from dh import get_files, mpf


def process_file(path):
    ansi_tmux_re = re.compile(
    path = Path(path)
        b"\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])|\\x08|\\x0C|\\x0F|\\x18|\\x1C|\\(\\d+[a-z]\\(B|\\(0[Bqtxl]\\(B"
    )
    status_re = re.compile(
        b"\\b\\d{4}[MGB]\\b|\\d{3,4}\\s+\\([^\\)]+\\)|\\[\\^\\]\\(B\\(0l\\(B<\\(0q\\(B\\s*\\d+|\\~\\\\/[^\\r\\n]*?\\s+\\$|\\(0mqq\\(B\\s+\\d+M\\s*/\\s*\\d+G"
    )
    try:
        content = path.read_bytes()
        content = status_re.sub(b"", content)
        content = ansi_tmux_re.sub(b"", content)
        text = content.decode("utf-8", errors="replace")
        cleaned_lines = []
        for line in text.splitlines(keepends=True):
            cleaned_line = re.sub("[\\x00-\\x08\\x0B\\x0C\\x0E-\\x1F\\x7F]", "", line)
            cleaned_lines.append(cleaned_line)
        result = "".join(cleaned_lines)
        path.write_text(result, encoding="utf-8")
        print(f"✓  {path.name}")
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd)
    mpf(process_file, files)


if __name__ == "__main__":
    main()
