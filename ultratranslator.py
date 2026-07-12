#!/data/data/com.termux/files/usr/bin/env python
import ast
import io
import re
import shutil
import sys
import tempfile
import tokenize
from collections.abc import Callable, Iterable
from multiprocessing import get_context
from os import scandir as os_scandir
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

from deep_translator import GoogleTranslator
from binaryornot import is_binary


CHUNK_SIZE = 4990
SKIP_DIRS = [".git", "__pycache__"]
MAX_WORKERS = 6

DOC_TH1 = '"""'
DOC_TH2 = "'''"
DOCTH = ('"""', "'''")

cwd = Path.cwd()
non_english_pattern = re.compile(r"[^\x00-\x7F]")


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


def get_nobinary(path: (str | Path)) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
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
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def translate_text(path) -> str:
    path = Path(path)
    return GoogleTranslator(source="auto", target="en").translate_file(path)


def safe_overwrite(filepath: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=filepath.parent) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    shutil.move(tmp_path, filepath)


def translate_python_file(path) -> str:
    print("  Analyzing Python structure...")
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"  Syntax error: {e}")
        return source

    result = []
    translated_count = 0

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return translate_text(source)

    source_lines = source.splitlines(keepends=True)
    prev_end = (1, 0)

    for token in tokens:
        tok_type, tok_str, start, end, line = token

        if start[0] > prev_end[0]:
            result.extend(source_lines[prev_end[0] : start[0]])
            result.append(line[: start[1]])
        elif start[1] > prev_end[1]:
            result.append(line[prev_end[1] : start[1]])

        if tok_type == tokenize.COMMENT and not is_english(tok_str):
            comment_text = tok_str[1:].strip()
            print(f"  Translating comment: {comment_text[:50]}...")
            translated = translate_text(comment_text)
            result.append(f"# {translated}")
            translated_count += 1

        elif tok_type == tokenize.STRING:
            stripped = tok_str.strip("'\"")
            if stripped and not is_english(stripped) and len(stripped) > 10:
                try:
                    print(f"  Translating string: {stripped[:50]}...")
                    translated = translate_text(stripped)

                    if tok_str.startswith((DOC_TH1, DOC_TH2)):
                        quote_char = tok_str[:3]
                    else:
                        quote_char = tok_str[0]

                    result.append(f"{quote_char}{translated}{quote_char}")
                    translated_count += 1
                except Exception as e:
                    print(f"  Error translating string: {e}")
                    result.append(tok_str)
            else:
                result.append(tok_str)
        else:
            result.append(tok_str)

        prev_end = end

    print(f"  Translated {translated_count} items")
    return "".join(result)


def process_file(path: str | Path) -> None:
    path = Path(path)
    print(f"  Processing {path.name}...")
    try:
        if path.suffix == ".py":
            translated = translate_python_file(path)
        else:
            translated = translate_text(path)

        if translated.strip() != original.strip():
            safe_overwrite(path, translated)
            print(f"  ✓ Updated {path.name}")
    except Exception as e:
        print(f"  Failed to process {path}: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_nobinary(cwd)
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    mpf_async(process_file, files)
