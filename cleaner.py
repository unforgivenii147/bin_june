#!/data/data/com.termux/files/usr/bin/python
import re
import sys
from pathlib import Path


def process_file(path) -> None:
    path = Path(path)

    # More comprehensive ANSI escape sequence regex
    ansi_re = re.compile(
        b"\x1b"  # ESC
        b"\["  # [
        b"[?]?"  # optional ?
        b"[0-9;]*"  # optional parameters (numbers and semicolons)
        b"[a-zA-Z]"  # final character
    )

    # Additional patterns for other escape sequences
    osc_re = re.compile(
        b"\x1b\]"  # OSC sequences (ESC ])
        b"[^\x07\x1b]*"  # content
        b"[\x07\x1b]"  # terminator
    )

    # DCS and other sequences
    misc_escape_re = re.compile(
        b"\x1b[PX^_][^\x1b]*\x1b\\\\"  # DCS, SOS, PM, APC
        b"|\x1b[@-_]"  # Other ESC sequences
    )

    # Carriage returns
    cr_re = re.compile(b"\r\n?|\n\r?")
    charset_re = re.compile(b"\x1b[()][0-9a-zA-Z]")
    try:
        content = path.read_bytes()

        content = charset_re.sub(b"", content)
        # Remove OSC sequences
        content = osc_re.sub(b"", content)
        # Remove DCS and misc escape sequences
        content = misc_escape_re.sub(b"", content)
        # Remove standard ANSI sequences
        content = ansi_re.sub(b"", content)
        # Normalize line endings (replace \r\n or \r with \n)
        content = cr_re.sub(b"\n", content)

        # Decode to text
        text = content.decode("utf-8", errors="replace")

        # Remove any remaining control characters
        cleaned_lines = []
        for line in text.splitlines(keepends=True):
            # Remove control characters except newlines and tabs
            cleaned_line = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", line)
            cleaned_lines.append(cleaned_line)

        result = "".join(cleaned_lines)
        path.write_text(result, encoding="utf-8")
        print(f"✓  {path.name}")
    except Exception as e:
        print(f"✗ Error processing {path.name}: {e}", file=sys.stderr)
        return


def get_files(path):
    return [p for p in path.glob("*.txt") if p.is_file()]


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd)
    for f in files:
        process_file(f)


if __name__ == "__main__":
    main()
