#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path


from pathlib import Path


def read_lines(path: (str | Path), ke: bool = True) -> list[str]:
    path = Path(path)
    if path.stat().st_size > THRESHOLD:
        return read_lines_mmap(path, ke)
    data = Path(path).read_bytes()
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=ke)
    if not lines[-1].endswith(("\n", "\r\n", "\r")) and data.endswith(b"\n"):
        lines.append("")
    return lines


def read_lines_mmap(path: Path, keep_ends: bool = True) -> list[str]:
    import mmap

    size = Path(path).stat().st_size
    with Path(path).open("rb") as f, mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ) as mm:
        text = mm[:].decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=keep_ends)
    if not lines[-1].endswith(("\n", "\r\n", "\r")) and size > 0 and text.endswith("\n"):
        lines.append("")
    return lines


if __name__ == "__main__":
    file_name = Path(sys.argv[1])
    nl = []
    target_char = sys.argv[2]
    for line in read_lines(file_name):
        stripped = line.strip()
        if stripped and target_char in stripped:
            indx = stripped.index(target_char)
            cleaned = stripped[indx - 1 :]
            nl.append(cleaned)
        elif stripped:
            nl.append(stripped)
    if nl:
        file_name.write_text("\n".join(nl), encoding="utf-8")
