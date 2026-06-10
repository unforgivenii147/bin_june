#!/data/data/com.termux/files/usr/bin/python

"""
Translate non-English lines in a file line by line using deep_translator.
The original file is updated in-place with translations shown alongside original lines.
"""

import os
import sys
import tempfile

from deep_translator import GoogleTranslator
from langdetect import DetectorFactory, detect

# Set seed for consistent language detection
DetectorFactory.seed = 0


def is_english(text):
    """
    Detect if a given text is English.
    Returns True if English, False otherwise.
    """
    if not text or text.strip() == "":
        return True  # Empty lines considered English

    try:
        lang = detect(text)
        return lang == "en"
    except:
        # If detection fails, assume it's English
        return True


def translate_line(line, translator, target_lang="en"):
    """
    Translate a single line to target language.
    Returns translated line or original if translation fails.
    """
    try:
        translated = translator.translate(line)
        return translated
    except Exception as e:
        print(f"Translation error for '{line[:50]}...': {e}", file=sys.stderr)
        return line


def process_file(filepath, show_translation=True):
    """
    path = Path(path)
    Process the file: detect non-English lines, translate them,
    and update the file in-place showing translations.
    """
    # Create backup
    backup_path = filepath + ".backup"

    try:
        # Read all lines from original file
        with open(filepath, "r", encoding="utf-8") as f:
            original_lines = f.readlines()

        # Create a temporary file for writing
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".tmp") as tmp_file:
            translator = GoogleTranslator(source="auto", target="en")

            for line_num, line in enumerate(original_lines, 1):
                original_line = line.rstrip("\n")

                # Check if the line contains non-English text
                if not is_english(original_line) and original_line.strip():
                    print(f"\n[Line {line_num}] Original: {original_line}")

                    # Translate the line
                    translated_line = translate_line(original_line, translator)

                    if show_translation:
                        print(f"[Line {line_num}] Translated: {translated_line}")
                        # Write both original and translation to file
                        tmp_file.write(f"{original_line} [TRANSLATION: {translated_line}]\n")
                    else:
                        # Replace with translation only
                        tmp_file.write(f"{translated_line}\n")
                else:
                    # Write original line as is
                    tmp_file.write(line)

        # Create backup before updating
        os.rename(filepath, backup_path)
        # Move temporary file to original path
        os.rename(tmp_file.name, filepath)

        print(f"\n✓ File updated successfully!")
        print(f"✓ Backup saved as: {backup_path}")

    except Exception as e:
        print(f"Error processing file: {e}", file=sys.stderr)
        if os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python translate_file.py <filename> [--replace]")
        print("  --replace: Replace original lines with translations (don't show original)")
        sys.exit(1)

    filepath = sys.argv[1]
    show_translation = True

    if len(sys.argv) > 2 and sys.argv[2] == "--replace":
        show_translation = False

    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found!", file=sys.stderr)
        sys.exit(1)

    print(f"Processing file: {filepath}")
    print("=" * 50)

    process_file(filepath, show_translation)


if __name__ == "__main__":
    main()
