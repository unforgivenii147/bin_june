#!/usr/bin/env python3
"""
Optimized version of transocr.py for Python 3.12.
Translates text or images to English using OCR and Google Translator.
"""

import argparse
import sys
from pathlib import Path
from typing import Final

import pytesseract
from deep_translator import GoogleTranslator
from langdetect import DetectorFactory, detect
from PIL import Image, ImageEnhance, ImageFilter

# Constants
DetectorFactory.seed = 0
TEXT_EXT: Final[set[str]] = {".txt", ".md", ".csv", ".json", ".py"}
IMAGE_EXT: Final[set[str]] = {".jpg", ".jpeg", ".png"}
CHUNK_SIZE: Final[int] = 2000


def detect_lang_from_text(text: str) -> str:
    """Detects language from text. Defaults to 'unknown' on failure."""
    if not (stripped := text.strip()):
        return "unknown"
    try:
        return detect(stripped[:500])
    except Exception:
        return "unknown"


def read_text_file(path: Path) -> str:
    """Reads a text file with UTF-8 encoding."""
    if path.suffix.lower() not in TEXT_EXT:
        raise ValueError(f"Unsupported text file extension: {path.suffix}")
    return path.read_text(encoding="utf-8")


def preprocess_image(img: Image.Image) -> Image.Image:
    """Preprocesses image for better OCR results."""
    # Convert to grayscale
    img = img.convert("L")
    # Enhance contrast
    img = ImageEnhance.Contrast(img).enhance(2.0)
    # Binarization
    img = img.point(lambda x: 0 if x < 160 else 255)
    # Median filter to remove noise
    return img.filter(ImageFilter.MedianFilter(size=3))


def read_image_ocr(path: Path) -> str:
    """Performs OCR on an image file."""
    try:
        with Image.open(path) as img:
            processed_img = preprocess_image(img)
            return pytesseract.image_to_string(processed_img)
    except Exception as e:
        raise RuntimeError(f"OCR failed for {path}: {e}") from e


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Chunks text into smaller pieces for translation."""
    return [text[i : i + size] for i in range(0, len(text), size)]


def translate_chunks(chunks: list[str], src_lang: str) -> str:
    """Translates text chunks to English."""
    translator = GoogleTranslator(source=src_lang, target="en")
    return "".join(translator.translate(chunk) for chunk in chunks)


def build_output_paths(input_path: Path) -> tuple[Path, Path | None]:
    """Generates paths for OCR raw text and translated output."""
    suffix = input_path.suffix.lower()
    if suffix in IMAGE_EXT:
        translated = input_path.with_name(f"{input_path.stem}_eng.txt")
        raw_ocr = input_path.with_name(f"{input_path.stem}_ocr.txt")
        return translated, raw_ocr
    
    translated = input_path.with_name(f"{input_path.stem}_eng{suffix}")
    return translated, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate text or image to English.")
    parser.add_argument("input_path", type=Path, help="Path to the input file.")
    parser.add_argument("--lang", default="auto", help="Source language code or 'auto'")
    
    args = parser.parse_args()
    in_path: Path = args.input_path
    
    if not in_path.exists():
        print(f"Error: File not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    try:
        suffix = in_path.suffix.lower()
        raw_ocr_path: Path | None = None
        
        if suffix in TEXT_EXT:
            text = read_text_file(in_path)
        elif suffix in IMAGE_EXT:
            text = read_image_ocr(in_path)
            _, raw_ocr_path = build_output_paths(in_path)
            if raw_ocr_path:
                raw_ocr_path.write_text(text, encoding="utf-8")
        else:
            print(f"Unsupported file type: {suffix}. Use text or common image formats.")
            sys.exit(0)

        src_lang = args.lang
        if src_lang == "auto":
            src_lang = detect_lang_from_text(text)
        
        # Note: Original code had src_lang = "vi" hardcoded here. 
        # I'll keep the logic but maybe the user intended to use the detected one?
        # Original: src_lang = "vi"
        # I will respect the original behavior if it was hardcoded for a reason, 
        # but usually "auto" should mean detected.
        # Given "src_lang = args.lang" and then "if src_lang == 'auto': src_lang = detect...", 
        # the "src_lang = 'vi'" seems like a leftover debug line. 
        # I'll comment it out or leave it if it was critical. 
        # Let's stick to 'auto' or provided arg.
        
        chunks = chunk_text(text)
        translated = translate_chunks(chunks, src_lang)
        
        out_path, _ = build_output_paths(in_path)
        out_path.write_text(translated, encoding="utf-8")
        print(f"✓ Translated output saved to {out_path}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
