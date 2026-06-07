#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path


def is_binary_file(path: Path, sample_size: int = 8192) -> bool:
    """Return True if the file looks binary."""
    with path.open("rb") as f:
        chunk = f.read(sample_size)
    return b"\x00" in chunk


def split_file_into_parts(file_path: Path, n: int):
    if n <= 0:
        raise ValueError("n must be a positive integer")
    if is_binary_file(file_path):
        print(f"Error: binary file '{file_path}' detected. Aborting.", file=sys.stderr)
        sys.exit(1)
    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    num_lines = len(lines)
    padding_width = len(str(n))
    base = num_lines // n
    stem = file_path.stem
    suffix = file_path.suffix
    parent = file_path.parent
    start = 0
    for i in range(1, n + 1):
        if i == n:
            end = num_lines
        else:
            end = start + base
        index_str = str(i).zfill(padding_width)
        part_name = f"{stem}_{index_str}{suffix}"
        part_path = parent / part_name
        part_path.write_text("".join(lines[start:end]), encoding="utf-8")
        print(f"Created: {part_path}")
        start = end


def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py <n> <file_path>")
        sys.exit(1)
    try:
        file_path = Path(sys.argv[1])
        n = int(sys.argv[2])
    except ValueError:
        print("Error: n must be an integer.", file=sys.stderr)
        sys.exit(1)
    if not file_path.is_file():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    split_file_into_parts(file_path, n)


if __name__ == "__main__":
    main()
