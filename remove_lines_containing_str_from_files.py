#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import sys
from pathlib import Path
from dh import get_nobinary

CHUNK_SIZE = 1024 * 1024


def is_binary(path: Path | str) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum((1 for b in chunk if b not in text_chars))
        return nontext / len(chunk) > 0.3
    except Exception:
        return True


STRTOFIND = ["dist-info", ".so", ".py", ".pth", "__", ".zip"]


def clean_text(text: str) -> str:
    return "\n".join((line for line in text.splitlines() if not any((s in line for s in STRTOFIND))))


def clean_file(path: str) -> None:
    try:
        original = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    cleaned = clean_text(original)
    if cleaned != original:
        Path(path).write_text(cleaned, encoding="utf-8")


def main() -> None:
    root = Path.cwd()
    isz = gsz(root)
    args = sys.argv[1:]
    files = [Path(arg) for arg in args] if args else get_nobinary(root)
    if len(files) == 1:
        clean_file(files[0])
        sys.exit(0)
    pool = Pool(8)
    for f in files:
        p.apply_async(clean_file, (f,))
    pool.close()
    pool.join()
    esz = gsz(root)
    diffsize = isz - esz
    print(f"space freed : {fsz(diffsize)}")


if __name__ == "__main__":
    main()


def gsz(path):
    try:
        return Path(path).stat().st_size
    except Exception:
        return 0
