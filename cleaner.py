#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import re
import sys


def clean_terminal_transcript(filepath):
    with open(filepath, encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Remove ANSI escape codes (colors, cursor movement, etc.)
    ansi_escape = re.compile(r"\x1b(\[[0-9;]*[mABCDEFGHJKSTfhilmnprsu]|\][^\x07]*\x07|[()][AB012])")
    content = ansi_escape.sub("", content)

    # Remove carriage returns (^M) used in terminal output
    content = content.replace("\r\n", "\n")
    content = content.replace("\r", "\n")

    # Remove backspace sequences (char + backspace)
    while "\x08" in content:
        content = re.sub(r".\x08", "", content)

    # Remove null bytes
    content = content.replace("\x00", "")

    # Remove other common control characters except newline and tab
    content = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", content)

    # Collapse 3+ consecutive blank lines into 2
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Strip trailing whitespace from each line
    content = "\n".join(line.rstrip() for line in content.splitlines())

    # Ensure file ends with a single newline
    content = content.rstrip("\n") + "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Cleaned: {filepath}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <transcript_file>")
        sys.exit(1)

    clean_terminal_transcript(sys.argv[1])
