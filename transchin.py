#!/data/data/com.termux/files/usr/bin/env python


import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from deep_translator import GoogleTranslator
from dh import get_nobinary

DIRECTORY = "."
CHUNK_SIZE = 2000

non_english_pattern = re.compile("[^\\x00-\\x7F]")


def split_into_chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def translate_chunk(chunk: str) -> str:
    try:
        result = GoogleTranslator(source="auto", target="en").translate(chunk)
        print(result)
        print("*" * 33)
        print()
        return result
    except Exception as e:
        print(f"Chunk translation error: {e}")
        return chunk


def translate_file(path: Path) -> None:
    try:
        content = Path(path).read_text(encoding="utf-8")
    except:
        print(f"Skipping unreadable file: {path}")
        return
    if not non_english_pattern.search(content):
        return
    chunks = split_into_chunks(content, CHUNK_SIZE)
    with ThreadPoolExecutor(max_workers=16) as executor:
        translated_chunks = list(executor.map(translate_chunk, chunks))
    translated_text = "".join(translated_chunks)
    try:
        path.write_text(translated_text, encoding="utf-8")
        print(f"Translated → {path.name}")
    except Exception as e:
        print(f"Error writing {new_path}: {e}")


def process_directory(directory: str) -> None:
    files = get_nobinary(directory)
    for f in files:
        translate_file(f)


if __name__ == "__main__":
    process_directory(DIRECTORY)
