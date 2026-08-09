#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import ast
import sys
from pathlib import Path

from dh import SOURCE_CODE_EXT, cprint, fsz, get_nobinary, mpf3

CHUNK_SIZE = 1024 * 1024


def remove_blank_lines(text) -> str:
    lines = text.splitlines(keepends=True)
    result_lines = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result_lines.append(line)
        prev_blank = is_blank
    return "".join(result_lines)


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


def gsz(path: str | Path) -> int:
    path = Path(path)
    total = 0
    if path.is_file():
        return path.stat().st_size
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


def process_file(path: Path) -> None:
    path = Path(path)
    if path.suffix == ".md":
        return
    removed: int = 0
    inline: int = 0
    if is_binary(path) or path.suffix in SOURCE_CODE_EXT:
        print(f"[skip] {path.name} is binary or source code")
        return
    before: int = gsz(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    print(f"{path.name}", end="|")
    if not lines:
        return
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#!") or "#!" in stripped:
            cleaned.append(line)
            continue
        if "#" in stripped and (not stripped.startswith("#")):
            indx = line.index("#")
            cleaned.append(line[:indx] + "\n")
            inline += 1
            continue
        if not stripped.startswith("#"):
            cleaned.append(line)
        else:
            removed += 1
    code = "".join(cleaned)
    code = remove_blank_lines(code)
    if path.suffix == ".py":
        try:
            _ = ast.parse(code)
            path.write_text(code, encoding="utf-8")
            diffsize = before - gsz(path)
            cprint(f"{fsz(diffsize)}|removed :{removed}|inline :{inline}", "yellow")
        except:
            cprint("result code invalid.", "magenta")
            return
    else:
        path.write_text(code, encoding="utf-8")
        diffsize = before - gsz(path)
        cprint(f"{fsz(diffsize)}|removed :{removed}|inline :{inline}", "yellow")


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(arg) for arg in args] if args else get_nobinary(cwd)
    if not files:
        print("no files found")
        return
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    before = gsz(cwd)
    _ = mpf3(process_file, files)
    diffsize = before - gsz(cwd)
    cprint(f"{fsz(diffsize)}", "cyan")


if __name__ == "__main__":
    main()
