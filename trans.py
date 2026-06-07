#!/data/data/com.termux/files/usr/bin/python

import argparse
import sys
from pathlib import Path

from deep_translator import GoogleTranslator, single_detection

CHUNK_SIZE = 2000
ALLOWED_EXT = {".txt", ".md", ".csv", ".json", ".py"}


def read_text_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(msg)
    return path.read_text(encoding="utf-8")


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def detect_lang(text: str) -> str:
    sample = text[:500]
    return single_detection(sample)


def translate_chunks(chunks: list[str], src_lang: str) -> str:
    translator = GoogleTranslator(source=src_lang, target="en")
    output = [translator.translate(chunk) for chunk in chunks]
    return "".join(output)


def write_text_file(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8")


def build_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_eng{input_path.suffix}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate text to English.")
    parser.add_argument("input_path")
    parser.add_argument("-g", "--game", default=None)
    parser.add_argument("--lang", default="auto", help="Source lang code or 'auto'")
    args = parser.parse_args()
    in_path = Path(args.input_path)
    if not in_path.exists():
        print(f"File not found: {in_path}", file=sys.stderr)
        sys.exit(1)
    try:
        text = read_text_file(in_path)
    except Exception as exc:
        print(f"Read error: {exc}", file=sys.stderr)
        sys.exit(1)
    chunks = chunk_text(text)
    src_lang = args.lang
    if src_lang == "auto":
        try:
            src_lang = detect_lang(text)
        except Exception as exc:
            print(f"Language detection error: {exc}", file=sys.stderr)
            sys.exit(1)
    try:
        translated = translate_chunks(chunks, src_lang)
    except Exception as exc:
        print(f"Translation error: {exc}", file=sys.stderr)
        sys.exit(1)
    out_path = build_output_path(in_path)
    try:
        write_text_file(out_path, translated)
    except Exception as exc:
        print(f"Write error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Translated ({src_lang} → en) → {out_path}")


if __name__ == "__main__":
    main()
