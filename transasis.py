#!/data/data/com.termux/files/usr/bin/python

import re
import sys
from pathlib import Path

from deep_translator import GoogleTranslator
from fastwalk import walk_files

DIRECTORY = "."
CHUNK_SIZE = 2000
TARGET_LANGUAGE = "en"
non_english_pattern = re.compile("[^\\x00-\\x7F]")


def chunk_text(text, chunk_size=CHUNK_SIZE):
    words = text.split()
    for i in range(0, len(words), chunk_size):
        yield " ".join(words[i : i + chunk_size])


def translate_text(text):
    try:
        return GoogleTranslator(source="auto", target=TARGET_LANGUAGE).translate(text)
    except Exception as e:
        print(f"Error translating text chunk: {e}")
        return text


def translate_file(filepath):
    content = Path(filepath).read_text(encoding="utf-8")
    if not non_english_pattern.search(content):
        print(f"No non-English content found in {filepath}, skipping.")
        return
    translated_chunks = []
    for chunk in chunk_text(content):
        translated_chunk = translate_text(chunk)
        translated_chunks.append(translated_chunk)
    translated_content = "\n\n".join(translated_chunks)
    new_filepath = Path(filepath).parent / f"translated_{Path(filepath).name}"
    new_filepath.write_text(translated_content, encoding="utf-8")
    print(f"saved as {new_filepath}")


def translate_folder(directory):
    for pth in walk_files(directory):
        path = Path(pth)
        if path.is_file():
            translate_file(path)


if __name__ == "__main__":
    choice = input("translate a f)ile or d)ir?")
    if choice == "d":
        translate_folder(DIRECTORY)
    elif choice == "f":
        fn = input("filename:").strip()
        translate_file(fn)
    else:
        print("enter d for dir and f for file.")
        sys.exit(1)
