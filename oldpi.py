#!/data/data/com.termux/files/usr/bin/env python
import argparse
import mmap
import re
import tokenize
from concurrent.futures import ThreadPoolExecutor, as_completed
from mmap import mmap
from os import scandir as os_scandir
from pathlib import Path

from tqdm import tqdm

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def is_python_file(path: (str | Path)) -> bool:
    from ast import parse as ast_parse

    path = Path(path)
    if is_binary(path):
        return False
    if not path.stat().st_size:
        return False
    if path.is_file() and path.suffix == ".py":
        return True
    if not path.suffix:
        content = path.read_text(encoding="utf-8")
        if not content:
            return False
        if content.startswith("#!") and "python" in content[:100]:
            return True
        try:
            _ = ast_parse(content)
            return True
        except:
            return False
    return False


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


def get_pyfiles(path: str | Path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        if path.suffix == ".py":
            return [path]
        if not path.suffix and not path.name.startswith(".") and is_python_file(path):
            return [path]
        return []

    if not path.is_dir():
        return []

    pyfiles = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        p = Path(entry.path)
                        if p.suffix == ".py":
                            pyfiles.append(p)
                        elif not p.suffix and not p.name.startswith(".") and is_python_file(p):
                            pyfiles.append(p)
        except (PermissionError, OSError):
            continue

    return sorted(pyfiles)


SIZE_THRESHOLD = 1 * 1024 * 1024
OLD_PRINT_RE = re.compile(r"(?m)^[ \t]*print[ \t]+[^(\n]")


def _open_source(path: str):
    size = Path(path).stat().st_size
    f = Path(path).open("rb")
    if size > SIZE_THRESHOLD:
        return mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    return f


def _read_text(path: str) -> str | None:
    try:
        with Path(path).open(encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None


def _has_rich_print_import(text: str) -> bool:
    return "from rich import print" in text


def regex_flag(path: str) -> bool:
    text = _read_text(path)
    if not text:
        return False
    if _has_rich_print_import(text):
        return False
    return bool(OLD_PRINT_RE.search(text))


def tokenizer_confirm(path: str) -> str | None:
    try:
        src = _open_source(path)
        tokens = list(tokenize.tokenize(src.readline))
    except Exception:
        return None
    for i, tok in enumerate(tokens):
        if tok.type == tokenize.NAME and tok.string == "print":
            line = tok.line.rstrip()
            if line.strip() == "print":
                continue
            j = i + 1
            while j < len(tokens) and tokens[j].type in {
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
            }:
                j += 1
            if j < len(tokens) and tokens[j].string != "(":
                return line
    return None


def autofix_file(path: str) -> bool:
    try:
        with Path(path).open(encoding="utf-8") as f:
            lines = f.readlines()
        if any(l.strip() == "from rich import print" for l in lines):
            return False
        changed = False
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.rstrip() == "print":
                continue
            if stripped.startswith("print ") and not stripped.startswith("print("):
                indent = line[: len(line) - len(stripped)]
                content = stripped[len("print ") :].rstrip()
                lines[i] = f"{indent}print({content})\n"
                changed = True
        if changed:
            with Path(path).open("w", encoding="utf-8") as f:
                f.writelines(lines)
        return changed
    except Exception:
        return False


def process_file(path: str, autofix: bool) -> tuple[str, str] | None:
    path = Path(path)
    if not regex_flag(path):
        return None
    confirmed = tokenizer_confirm(path)
    if not confirmed:
        return None
    if autofix:
        autofix_file(path)
    return path, confirmed


def main() -> None:
    parser = argparse.ArgumentParser(description="Regex + tokenizer detection of Python 2 print")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("-a", "--autofix", action="store_true")
    args = parser.parse_args()

    py_files = get_pyfiles(args.path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_file, f, args.autofix) for f in py_files]
        for future in tqdm(as_completed(futures), total=len(futures), desc="", unit="file"):
            result = future.result()
            if result:
                path, line = result
                print(f"{path}\n  {line}")


if __name__ == "__main__":
    main()
