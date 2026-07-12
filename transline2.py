#!/data/data/com.termux/files/usr/bin/env python


import re
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterable
from multiprocessing import get_context
from os import scandir as os_scandir
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

from deep_translator import GoogleTranslator

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


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


cwd = Path.cwd()
non_english_pattern = re.compile(r"[^\x00-\x7F]")


def is_english(text: str) -> bool:
    return not non_english_pattern.search(text)


def chunk_text(text: str, size: int = 800) -> list[str]:
    if not text or size <= 0:
        return [text] if text else []
    chunks = []
    for i in range(0, len(text), size):
        chunks.append(text[i : i + size])
    return chunks


def translate_chunk(chunk: str) -> str:
    if not chunk or is_english(chunk):
        return chunk
    try:
        result = GoogleTranslator(source="auto", target="en").translate(chunk)
        print(result)
        return result if result else chunk
    except Exception as e:
        print(f"  Translation error: {e}")
        return chunk


def translate_text(text: str) -> str:
    if not text:
        return text
    lines = text.split("\n")
    translated_lines = []
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line or is_english(stripped_line):
            translated_lines.append(line)
        else:
            try:
                result = GoogleTranslator(source="auto", target="en").translate(line)
                print(result)
                translated_lines.append(result if result else line)
            except Exception as e:
                print(f"  Translation error on line: {e}")
                translated_lines.append(line)
    return "\n".join(translated_lines)


def safe_overwrite(filepath: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=filepath.parent) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    shutil.move(tmp_path, filepath)


def process_file(path: str | Path) -> None:
    path = Path(path)
    try:
        original = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"  Error reading {path}: {e}")
        return

    if is_english(original.strip()):
        return

    print(f"  Processing {path.name}...")
    try:
        translated = translate_text(original)

        if translated.strip() != original.strip():
            safe_overwrite(path, translated)
            print(f"  ✓ Updated {path.name}")
    except Exception as e:
        print(f"  Failed to process {path}: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".md", ".txt"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    mpf_async(process_file, files)
