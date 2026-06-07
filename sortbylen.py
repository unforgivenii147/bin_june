#!/data/data/com.termux/files/usr/bin/python


def sort_by_length(lines: list[str]) -> list[str]:
    return sorted(lines, key=len)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from dh import read_lines

    path = Path(sys.argv[1].strip())
    bakpath = path.with_name(path.stem + "_sorted" + path.suffix)
    lines = read_lines(path, ke=True)
    sorted_lines = sort_by_length(lines)
    bakpath.write_text("".join(sorted_lines), encoding="utf8")
    del sorted_lines, lines, path, bakpath
