#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import io
import re
import sys
import tokenize
from os import scandir as os_scandir
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
from dh import mpf3


def is_python_file(path: str | Path) -> bool:
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


def get_pyfiles(path: str | Path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        if path.suffix == ".py":
            return [path]
        if not path.suffix and (not path.name.startswith(".")) and is_python_file(path):
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
                        elif not p.suffix and (not p.name.startswith(".")) and is_python_file(p):
                            pyfiles.append(p)
        except (PermissionError, OSError):
            continue
    return sorted(pyfiles)


def remove_comments_and_docstrings(source_code: str) -> str:
    io_obj = io.StringIO(source_code)
    out = ""
    prev_toktype = tokenize.INDENT
    last_lineno = -1
    last_col = 0
    for tok in tokenize.generate_tokens(io_obj.readline):
        toktype = tok[0]
        tok_string = tok[1]
        start_lineno, start_col = tok[2]
        _end_lineno, end_col = tok[3]
        if start_lineno > last_lineno:
            last_col = 0
        if toktype == tokenize.COMMENT or (toktype == tokenize.STRING and prev_toktype == tokenize.INDENT):
            pass
        else:
            if start_col > last_col:
                out += " " * (start_col - last_col)
            out += tok_string
            prev_toktype = toktype
            last_col = end_col
            last_lineno = start_lineno
    return out


def shorten_variable_name(name):
    if not name or name.startswith("_"):
        return name
    vowels = "aeiouAEIOU"
    return "".join([char for char in name if char not in vowels])


def process_file(path) -> None:
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    content_no_comments = remove_comments_and_docstrings(content)
    lines = content_no_comments.splitlines()
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    "\n".join(non_empty_lines)
    import keyword

    keywords = set(keyword.kwlist)

    def replacer(match):
        name = match.group(0)
        if name in keywords:
            return name
        return shorten_variable_name(name)

    content_no_multiline_strings = re.sub("'''.*?'''|\\\"\\\"\\\".*?\\\"\\\"\\\"", "", content, flags=re.DOTALL)
    content_no_comments_single = re.sub("#.*", "", content_no_multiline_strings)
    lines = content_no_comments_single.splitlines()
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    final_content = "\n".join(non_empty_lines)
    compressed_path = path.with_stem(path.stem + "_compressed")
    compressed_path.write_text(final_content, encoding="utf-8")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = []
    if args:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(get_pyfiles(p))
    else:
        files = get_pyfiles(cwd)
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)
