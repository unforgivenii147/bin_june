#!/data/data/com.termux/files/usr/bin/env python


"""
Recursively translate non‑English text files to English using Google Translate.
- Accepts multiple files/directories as input (defaults to current directory).
- Processes all text-based files without extension restrictions.
- Splits file content into chunks < 5000 characters.
- Validates translated Python files with ast.parse; skips writing on error.
- Prints translated text live.
- Parallel file processing with multiprocessing.
- Rate‑limiting delay between chunk translations.
"""

import argparse
import ast
import os
import time
from multiprocessing import Pool
from pathlib import Path
from deep_translator import GoogleTranslator


def is_text_file(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
            return not is_binary(chunk)
    except (OSError, IOError):
        return False


def is_binary(chunk: bytes) -> bool:
    if not chunk:
        return False
    return b"\x00" in chunk[:8192]


def chunk_lines(lines: list, max_len: int = 5000):
    current_chunk = []
    current_len = 0
    for line in lines:
        line_len = len(line)
        if current_len + line_len > max_len and current_chunk:
            yield "".join(current_chunk)
            current_chunk = [line]
            current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len
    if current_chunk:
        yield "".join(current_chunk)


def translate_file(args_tuple: tuple) -> None:
    file_path, target_lang, delay, output_dir = args_tuple
    file_path = Path(file_path)
    print(f"[{os.getpid()}] Processing: {file_path}")
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except (UnicodeDecodeError, OSError) as e:
        print(f"  ✗ Cannot read: {file_path} ({e})")
        return
    if not content.strip():
        print(f"  ⊘ Empty file, skipping: {file_path}")
        return
    lines = content.splitlines(keepends=True)
    chunks = list(chunk_lines(lines, max_len=5000))
    translator = GoogleTranslator(source="auto", target=target_lang)
    translated_chunks = []
    for i, chunk in enumerate(chunks, 1):
        try:
            translated = translator.translate(chunk)
        except Exception as e:
            print(f"  ✗ Translation error in chunk {i}/{len(chunks)}: {e}")
            return
        preview = translated[:100] + ("…" if len(translated) > 100 else "")
        print(f"    [{i}/{len(chunks)}] {preview}")
        translated_chunks.append(translated)
        if i < len(chunks):
            time.sleep(delay)
    translated_text = "".join(translated_chunks)
    if file_path.suffix.lower() == ".py":
        try:
            ast.parse(translated_text)
            print(f"  ✓ Python syntax valid")
        except SyntaxError as e:
            print(f"  ✗ Syntax error in translated Python, NOT writing: {e}")
            return
    if output_dir:
        try:
            rel_path = file_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = file_path
        out_path = (output_dir / rel_path).with_suffix(file_path.suffix + f".{target_lang}")
    else:
        out_path = file_path.with_suffix(file_path.suffix + f".{target_lang}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_path.write_text(translated_text, encoding="utf-8")
        print(f"  → Written: {out_path}\n")
    except OSError as e:
        print(f"  ✗ Cannot write output: {out_path} ({e})\n")


def collect_files(paths: list) -> list:
    files = []
    for path_input in paths:
        path = Path(path_input).resolve()
        if path.is_file():
            if is_text_file(path):
                files.append(path)
        elif path.is_dir():
            for file_path in path.rglob("*"):
                if file_path.is_file() and is_text_file(file_path):
                    files.append(file_path)
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description="Translate text files recursively using Google Translate.")
    parser.add_argument(
        "paths", nargs="*", type=str, help="Files or directories to process (defaults to current directory)"
    )
    parser.add_argument("--target-lang", default="en", help="Target language code (default: en)")
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Delay in seconds between chunk translations (default: 1.0)"
    )
    parser.add_argument(
        "--workers", type=int, default=None, help=f"Number of parallel workers (default: {os.cpu_count()})"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for translated files (default: same folder with language suffix)",
    )
    args = parser.parse_args()
    paths = args.paths if args.paths else ["."]
    workers = args.workers or os.cpu_count()
    files = collect_files(paths)
    if not files:
        print("No text files found.")
        return
    print(f"Found {len(files)} text files.\n")
    tasks = [(f, args.target_lang, args.delay, args.output_dir) for f in files]
    with Pool(processes=workers) as pool:
        pool.map(translate_file, tasks)
    print("✓ All files processed.")


if __name__ == "__main__":
    main()
