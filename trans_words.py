#!/data/data/com.termux/files/usr/bin/env python
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import langdetect
from deep_translator import GoogleTranslator

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def chunk_file(file_path, chunk_size=4500):
    chunks = []
    current_chunk = ""
    start_line = 0
    current_line = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f):
            if len(current_chunk) + len(line) > chunk_size and current_chunk:
                chunks.append((start_line, current_line - 1, current_chunk))
                current_chunk = line
                start_line = current_line
            else:
                current_chunk += line
            current_line += 1

        if current_chunk:
            chunks.append((start_line, current_line - 1, current_chunk))

    return chunks


def detect_language(text):
    try:
        return langdetect.detect(text[:500])
    except:
        return None


def translate_chunk(chunk_data, chunk_index, total_chunks):
    start_line, end_line, text = chunk_data

    if chunk_index > 0:
        time.sleep(1)

    lang = detect_language(text)

    if lang == "en":
        return {
            "chunk_id": f"{start_line}_{end_line}",
            "start_line": start_line,
            "end_line": end_line,
            "translated": text,
            "skipped": True,
        }

    try:
        translator = GoogleTranslator(source_language="auto", target_language="en")
        translated = translator.translate(text)

        return {
            "chunk_id": f"{start_line}_{end_line}",
            "start_line": start_line,
            "end_line": end_line,
            "translated": translated,
            "skipped": False,
        }
    except Exception as e:
        print(f"Error translating chunk {start_line}_{end_line}: {e}")
        return None


def process_file(file_path):
    print(f"\nProcessing: {file_path}")

    chunks = chunk_file(file_path)
    print(f"Total chunks: {len(chunks)}")

    translations = []

    with ProcessPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(translate_chunk, chunk, idx, len(chunks)) for idx, chunk in enumerate(chunks)]

        completed = 0
        for future in as_completed(futures):
            result = future.result()
            if result:
                translations.append(result)
            completed += 1
            print(f"Progress: {completed}/{len(chunks)}")

    output_file = file_path.stem + ".json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"lines": sorted(translations, key=lambda x: x["start_line"])}, f, ensure_ascii=False, indent=2)

    print(f"Output: {output_file}")


def get_input_files(paths):
    files = []

    if not paths:
        paths = [Path.cwd()]

    for path in paths:
        p = Path(path)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(p.rglob("*.txt"))

    return files


def main():
    input_paths = sys.argv[1:] if len(sys.argv) > 1 else []

    files = get_input_files(input_paths)

    if not files:
        print("No text files found")
        return

    for file_path in files:
        try:
            process_file(file_path)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    main()
