#!/data/data/com.termux/files/usr/bin/python

import re
from pathlib import Path
from dh import cprint, get_filez, is_binary

COLOR_RE = re.compile("#([a-fA-F0-9]{6}|[a-fA-F0-9]{3})\\b")


def pf(path: Path):
    content = path.read_text(encoding="utf-8", errors="ignore")
    found = []
    found = COLOR_RE.findall(content)
    found = list(set(found))
    if found:
        print(f"{path.name}", end=" : ")
        cprint(f"{len(found)}", "cyan")
        return found
    return []


def main() -> None:
    cwd = Path.cwd()
    outfile = cwd / "colors"
    colorz = set()
    for path in get_filez(cwd):
        if not is_binary(path):
            result = pf(path)
            if result:
                colorz.update(result)
    colors = sorted(colorz)
    fc = len(colors)
    for c in colors:
        if len(c) == 3:
            normed = c * 2
            colors.append(normed)
    finals = []
    for k in sorted(set(colors)):
        if len(k) == 3:
            continue
        finals.append(k)
    finals = sorted(set(finals))
    outfile.write_text("\n".join(finals), encoding="utf-8")
    cprint(f"{fc} colors found", "green")


if __name__ == "__main__":
    main()
