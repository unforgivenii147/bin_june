#!/data/data/com.termux/files/usr/bin/env python

import ast
import sys
from collections.abc import Callable, Iterable
from multiprocessing import get_context
from os import scandir as os_scandir
from pathlib import Path
from typing import Any

import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Query, QueryCursor

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def remove_blank_lines(text: str | Path) -> str:
    content = text
    if isinstance(text, Path):
        content = text.read_text(encoding="utf-8")

    if not isinstance(text, (str, Path)):
        return str(text)

    if isinstance(text, str) and Path(text).exists():
        content = Path(text).read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    result_lines = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result_lines.append(line)
        prev_blank = is_blank
    return "".join(result_lines)


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
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > 0.3
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


def mpf_async(func: Callable[[Any], Any], items: Iterable[Any]):
    with get_context("spawn").Pool(MAX_WORKERS) as p:
        async_results = [p.apply_async(func, (item,)) for item in items]
        results = []
        for i, async_result in enumerate(async_results):
            try:
                results.append(async_result.get(timeout=30))
            except Exception as e:
                print(f"Item {i} failed: {e}")
                results.append(None)
        return results


mpf = mpf_async

QUERY_STRING = """
(comment) @comment
(block
  . (expression_statement
    (string)) @docstring)
(module
  . (expression_statement
    (string)) @docstring)
"""


class TSRemover:
    def __init__(self) -> None:
        self.language = Language(tspython.language())
        self.parser = Parser(self.language)
        self.query = Query(self.language, QUERY_STRING)

    def remove_comments(self, source: str) -> tuple[str, int, int]:
        source_bytes = source.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        cursor = QueryCursor(self.query)
        matches = cursor.matches(tree.root_node)
        deletions = []
        comment_count = 0
        docstring_count = 0
        for _pattern_index, captures_dict in matches:
            for capture_name, node_list in captures_dict.items():
                for node in node_list:
                    start = node.start_byte
                    end = node.end_byte
                    text = source_bytes[start:end].decode("utf-8")
                    if capture_name == "comment":
                        stripped = text.strip()
                        if stripped.startswith(("# type:", "# TODO", "# noqa", "#!", "# fmt:")):
                            continue
                        comment_count += 1
                    else:
                        docstring_count += 1
                    if end < len(source_bytes) and source_bytes[end : end + 1] == b"\n":
                        end += 1
                    deletions.append((start, end))
        deletions = sorted(set(deletions), reverse=True)
        new_source = source_bytes
        for start, end in deletions:
            new_source = new_source[:start] + new_source[end:]
        cleaned = new_source.decode("utf-8")
        cleaned = remove_blank_lines(cleaned)
        return cleaned, comment_count, docstring_count


def process_file(path) -> None:
    path = Path(path)
    ts_rmc = TSRemover()
    code = path.read_text(encoding="utf-8", errors="ignore")
    ts_rmc.remove_comments(code)
    result, comments, docstrings = ts_rmc.remove_comments(code)
    if comments == 0 and docstrings == 0:
        print(f"[NO CHANGE] : {path.name}")
        return
    try:
        ast.parse(result)
        print(f"{path.name}: comments: {comments}   docstrings: {docstrings}")
        path.write_text(result, encoding="utf-8")
    except:
        print(f"{path.name} : invalid code")


def main() -> None:
    cwd = Path.cwd()
    before = gsz(".")
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_pyfiles(cwd)
    print(f"Processing {len(files)} files using QueryCursor...")
    mpf(process_file, files)
    diff_size = before - gsz(".")
    if diff_size != 0:
        print(fsz(diff_size))


if __name__ == "__main__":
    main()
