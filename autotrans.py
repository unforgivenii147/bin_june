#!/data/data/com.termux/files/usr/bin/env python


import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from deep_translator import GoogleTranslator
from fastwalk import walk_files


from pathlib import Path


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


DIRECTORY = "."
CHUNK_SIZE = 2000
non_english_pattern = re.compile(r"[^\x00-\x7F]")


def split_into_chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def translate_chunk(chunk: str) -> str:
    try:
        return GoogleTranslator(source="auto", target="en").translate(chunk)
    except Exception as e:
        print(f"[ERROR] Chunk translation failed: {e}")
        return chunk


def contains_non_english(text: str) -> bool:
    return bool(non_english_pattern.search(text))


def translate_file(path: Path) -> None:
    print(f"\n[INFO] Processing file: {path}")
    try:
        content = Path(path).read_text(encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] Cannot read file {path}: {e}")
        return
    if not contains_non_english(content):
        print(f"[SKIP] File is already English: {path.name}")
        return
    print(f"[INFO] Non-English content detected in: {path.name}")
    print(f"[INFO] Splitting into chunks of {CHUNK_SIZE} characters")
    chunks = split_into_chunks(content, CHUNK_SIZE)
    print(f"[INFO] Total chunks: {len(chunks)}")
    print("[INFO] Translating chunks in parallel...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        translated_chunks = list(executor.map(translate_chunk, chunks))
    translated_text = "".join(translated_chunks)
    new_name = f"{path.stem}_eng{path.suffix}"
    new_path = path.parent / new_name
    print(f"[INFO] Writing translated output to: {new_path}")
    try:
        Path(new_path).write_text(translated_text, encoding="utf-8")
        print(f"[DONE] Translated → {new_path.name}")
    except Exception as e:
        print(f"[ERROR] Failed to write output file {new_path}: {e}")


def process_directory(directory: str) -> None:
    print(f"[INFO] Scanning directory: {directory}")
    files = []
    for pth in walk_files(directory):
        path = Path(pth)
        if path.is_file() and not is_binary(path):
            files.append(path)
            print(f"[FOUND] Text file: {path}")
    print(f"\n[INFO] Total text files found: {len(files)}")
    print("[INFO] Starting parallel file translation...\n")
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(translate_file, f): f for f in files}
        for future in as_completed(futures):
            f = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"[ERROR] Unexpected error processing {f}: {e}")


if __name__ == "__main__":
    process_directory(DIRECTORY)
