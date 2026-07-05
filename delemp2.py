#!/data/data/com.termux/files/usr/bin/python


import sys
from pathlib import Path
from dh import get_nobinary


def clean_lines(lines: list[str], collapse: bool) -> tuple[list[str], int]:
    removed = 0
    if not collapse:
        cleaned = [l for l in lines if l.strip()]
        removed = len(lines) - len(cleaned)
        return cleaned, removed
    cleaned = []
    blank_run = 0
    for line in lines:
        if line.strip():
            blank_run = 0
            cleaned.append(line)
        else:
            blank_run += 1
            if blank_run == 1:
                cleaned.append(line)
            else:
                removed += 1
    return cleaned, removed


def process_file(path: Path, collapse: bool) -> tuple[bool, int, str]:
    print(f"processing {path.name}")
    path = Path(path)
    try:
        with Path(path).open(encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        cleaned, removed = clean_lines(lines, collapse)
        if removed == 0:
            return False, 0, ""
        with Path(path).open("w", encoding="utf-8", errors="ignore") as f:
            f.writelines(cleaned)
        return True, removed, path.suffix.lower()
    except Exception:
        return False, 0, ""


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_nobinary(cwd)
    for f in files:
        process_file(f, collapse=True)


if __name__ == "__main__":
    main()
