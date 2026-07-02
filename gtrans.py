#!/data/data/com.termux/files/usr/bin/env python
"""
Translate mixed-language files containing Tamil and English text.
Handles lines with Tamil, Tamil commentaries, and English translations.
"""

from googletrans import Translator
import sys
import re
import time


def translate_text(text, target_lang="en"):
    """Translate text to target language using Google Translate."""
    if not text or text.strip() == "":
        return text

    try:
        translator = Translator()
        # Detect if text is mostly Tamil
        # Google Translate handles mixed languages automatically
        translated = translator.translate(text, dest=target_lang)
        return translated.text
    except Exception as e:
        print(f"Translation error: {e}", file=sys.stderr)
        return f"[Translation failed: {text}]"


def process_file(input_file, output_file=None, translate_tamil=True):
    """
    Process a file and translate Tamil lines to English.

    Args:
        input_file: Path to input file
        output_file: Path to output file (if None, print to stdout)
        translate_tamil: If True, translate Tamil text
    """
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.", file=sys.stderr)
        return
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return

    output_lines = []

    # Simple pattern to detect English text (basic heuristic)
    english_pattern = re.compile(r'^[A-Za-z0-9\s\.,;:!?\'"()-]+$')

    for i, line in enumerate(lines):
        line = line.rstrip("\n")
        original_line = line

        # Skip empty lines or lines with just whitespace
        if not line.strip():
            output_lines.append(line)
            continue

        # Check if line already appears to be English
        is_english = english_pattern.match(line.strip())

        # Check for separator lines
        if line.strip() == "%":
            output_lines.append(line)
            continue

        # Handle numbered Tamil lines (like "1. அகர முதல...")
        # and Tamil commentary lines
        if not is_english and translate_tamil:
            # Translate the line
            print(f"Translating line {i + 1}...", file=sys.stderr)
            translated = translate_text(line)

            # Add original and translation with a marker
            output_lines.append(f"{line}")
            output_lines.append(f"→ {translated}")
            output_lines.append("")  # Add a blank line for readability

            # Be nice to Google's API rate limits
            time.sleep(0.5)
        else:
            # Keep English or non-Tamil lines as-is
            output_lines.append(line)

    # Write output
    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(output_lines))
            print(f"Output written to: {output_file}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
    else:
        # Print to stdout
        print("\n".join(output_lines))


def main():
    """Main function with command-line argument handling."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Translate Tamil text in files to English while preserving English content."
    )
    parser.add_argument("input_file", help="Path to the input file to translate")
    parser.add_argument("-o", "--output", help="Path to output file (default: print to stdout)", default=None)
    parser.add_argument("--no-translate", action="store_true", help="Do not translate Tamil text (just keep original)")

    args = parser.parse_args()

    process_file(args.input_file, args.output, translate_tamil=not args.no_translate)


if __name__ == "__main__":
    main()
