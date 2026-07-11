#!/data/data/com.termux/files/usr/bin/env python
import argparse
import mmap
import re
import tokenize
from concurrent.futures import ThreadPoolExecutor, as_completed
from mmap import mmap
from pathlib import Path
from dh import get_pyfiles
from tqdm import tqdm

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
