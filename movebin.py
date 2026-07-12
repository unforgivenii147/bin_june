#!/data/data/com.termux/files/usr/bin/env python


import shutil
from pathlib import Path


from pathlib import Path


def is_binary(path: (Path | str)) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def main() -> None:
    cwd = Path.cwd()
    binary_dir = cwd / "binary"
    binary_dir.mkdir(exist_ok=True)
    files_moved = 0
    for f in cwd.iterdir():
        if f.is_file() and is_binary(Path(f)):
            try:
                shutil.move(str(f), binary_dir / f.name)
                print(f"Moved: {f.name} -> binary/{f.name}")
                files_moved += 1
            except Exception as e:
                print(f"Failed to move {f.name}: {e}")
    if files_moved == 0:
        print("No binary files found to move.")
    else:
        print(f"Total binary files moved: {files_moved}")


if __name__ == "__main__":
    main()
