#!/data/data/com.termux/files/usr/bin/env python


"""
Optimized version of trans_file_linebyline.py for Python 3.12.
Translates non-English lines in a file line by line in-place.
"""

import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Final
from deep_translator import GoogleTranslator
from langdetect import DetectorFactory, detect

DetectorFactory.seed = 0
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def is_english(text: str) -> bool:
    if not (stripped := text.strip()):
        return True
    try:
        return detect(stripped) == "en"
    except Exception:
        return True


def translate_line(line: str) -> str:
    try:
        translator = GoogleTranslator(source="auto", target="en")
        result = translator.translate(line.strip())
        return result if result else line
    except Exception as e:
        logger.error("Translation error: %s", e)
        return line


def process_file(filepath: Path, replace_original: bool = False) -> None:
    if not filepath.exists():
        logger.error("File not found: %s", filepath)
        return
    backup_path = filepath.with_suffix(filepath.suffix + ".backup")
    shutil.copyfile(filepath, backup_path)
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=filepath.parent) as tmp_file:
            for i, line in enumerate(lines, 1):
                stripped = line.rstrip("\n")
                if stripped.strip() and (not is_english(stripped)):
                    translated = translate_line(stripped)
                    if not replace_original:
                        tmp_file.write(f"{stripped} [TRANSLATION: {translated}]\n")
                    else:
                        tmp_file.write(f"{translated}\n")
                    logger.info("Line %d translated.", i)
                else:
                    tmp_file.write(line)
        shutil.move(tmp_file.name, filepath)
        logger.info("✓ File updated successfully: %s", filepath.name)
        logger.info("✓ Backup saved as: %s", backup_path.name)
    except Exception as e:
        logger.error("Error processing file %s: %s", filepath, e)
        if "tmp_file" in locals() and Path(tmp_file.name).exists():
            Path(tmp_file.name).unlink()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python trans_file_linebyline_optimized.py <filename> [--replace]")
        print("  --replace: Replace original lines with translations")
        sys.exit(1)
    filepath = Path(sys.argv[1])
    replace_original = "--replace" in sys.argv
    logger.info("Processing file: %s", filepath)
    process_file(filepath, replace_original)


if __name__ == "__main__":
    main()
