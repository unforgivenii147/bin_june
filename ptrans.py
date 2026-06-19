#!/data/data/com.termux/files/usr/bin/python
"""
Recursively translate non‑English text files to English using Google Translate.
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

# --- Default configuration ---
DEFAULT_TEXT_EXTENSIONS = {
    ".txt",
    ".py",
    ".md",
    ".html",
    ".css",
    ".js",
    ".json",
    ".xml",
    ".csv",
    ".yaml",
    ".yml",
    ".cfg",
    ".ini",
    ".sh",
    ".bat",
    ".tex",
    ".rst",
    ".log",
    ".conf",
}


def chunk_lines(lines, max_len=5000):
    """
    Split a list of lines (with trailing newlines) into chunks that
    do not exceed `max_len` characters, without breaking a line.
    """
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


def translate_file(file_path: Path, target_lang: str, delay: float, output_dir: Path = None) -> None:
    """
    Read a text file, translate its content in chunks, and write the
    translated version.  For .py files the result is validated with
    ast.parse; if invalid the file is not written.
    """
    print(f"[{os.getpid()}] Processing: {file_path}")

    # Read file with UTF-8
    try:
        content = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"  Skipping (cannot read): {file_path}  ({e})")
        return

    # Split into lines (keep line endings) then into chunks
    lines = content.splitlines(keepends=True)
    chunks = list(chunk_lines(lines, max_len=5000))

    if not chunks:
        print(f"  Empty file, skipping: {file_path}")
        return

    # Create a translator (reuses sessions, auto-detect source)
    translator = GoogleTranslator(source="auto", target=target_lang)

    translated_chunks = []
    for i, chunk in enumerate(chunks, 1):
        try:
            # Translate chunk
            translated = translator.translate(chunk)
        except Exception as e:
            print(f"  Translation error in chunk {i}/{len(chunks)} of {file_path.name}: {e}")
            return  # skip whole file on any API failure

        # Live progress: show up to 120 chars of the translated chunk
        preview = translated[:120] + ("..." if len(translated) > 120 else "")
        print(f"    Chunk {i}/{len(chunks)}: {preview}")

        translated_chunks.append(translated)

        # Rate-limiting delay
        time.sleep(delay)

    # Reassemble full translated text (chunks already contain newlines)
    translated_text = "".join(translated_chunks)

    # Python syntax check
    if file_path.suffix.lower() == ".py":
        try:
            ast.parse(translated_text)
        except SyntaxError as e:
            print(f"  ✗ Syntax error in translated Python file, NOT writing: {file_path}")
            print(f"    {e}")
            return
        else:
            print(f"  ✓ Python syntax valid")

    # Determine output path
    if output_dir:
        # Preserve relative directory structure
        try:
            rel_path = file_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = file_path
        out_path = output_dir / rel_path.with_suffix(file_path.suffix + f".{target_lang}")
    else:
        out_path = file_path.with_suffix(file_path.suffix + f".{target_lang}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_path.write_text(translated_text, encoding="utf-8")
        print(f"  → Written: {out_path}")
    except OSError as e:
        print(f"  ✗ Could not write output: {out_path}  ({e})")


def is_text_file(path: Path, extensions: set) -> bool:
    """Check if the file has a known text extension (case‑insensitive)."""
    return path.suffix.lower() in extensions


def main():
    parser = argparse.ArgumentParser(description="Translate non‑English text files recursively using Google Translate.")
    parser.add_argument("directory", type=Path, help="Root directory to scan recursively")
    parser.add_argument("--target-lang", default="en", help="Target language code (default: en)")
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Delay in seconds between chunk translations (default: 1.0)"
    )
    parser.add_argument(
        "--workers", type=int, default=os.cpu_count(), help="Number of parallel worker processes (default: CPU count)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to store translated files (default: same folder with '.en' suffix)",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=None,
        help="File extensions to process (e.g. .py .txt .md). If omitted, a built‑in list is used.",
    )
    args = parser.parse_args()

    # Build extension set
    if args.extensions:
        extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in args.extensions}
    else:
        extensions = DEFAULT_TEXT_EXTENSIONS

    root = args.directory.resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory.")
        return

    # Collect all matching files
    files = [f for f in root.rglob("*") if f.is_file() and is_text_file(f, extensions)]
    print(f"Found {len(files)} text files to process.\n")

    # Process files in parallel
    with Pool(processes=args.workers) as pool:
        # Use starmap to pass multiple arguments to translate_file
        pool.starmap(translate_file, [(f, args.target_lang, args.delay, args.output_dir) for f in files])

    print("\nAll files processed.")


if __name__ == "__main__":
    main()
