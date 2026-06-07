#!/data/data/com.termux/files/usr/bin/python

import os
import re
import sys
import tempfile

THRESHOLD = 5 * 1024 * 1024
RE_REPEAT = re.compile("^(.)\\1+$", re.IGNORECASE)


def should_skip(line: str) -> bool:
    s = line.rstrip("\n")
    return bool(RE_REPEAT.fullmatch(s))


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <wordlist.txt>", file=sys.stderr)
        sys.exit(1)
    fname = sys.argv[1]
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="wordlist_", suffix=".tmp")
    try:
        with (
            os.fdopen(tmp_fd, "w", encoding="utf-8", errors="ignore") as out,
            open(fname, "r", encoding="utf-8", errors="ignore") as inp,
        ):
            for line in inp:
                if not should_skip(line):
                    out.write(line)
        os.replace(tmp_name, fname)
    except Exception:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()
