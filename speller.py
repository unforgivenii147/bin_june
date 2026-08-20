#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import argparse
import re

from spellchecker import SpellChecker


def process_file(filepath, autofix=False):
    spell = SpellChecker()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found.")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    misspelled_count = 0

    def check_and_replace(match):
        nonlocal misspelled_count
        word = match.group(0)
        if not word.isalpha():
            return word
        if word.lower() not in spell:
            misspelled_count += 1
            if autofix:
                correction = spell.correction(word.lower())
                if not correction:
                    return word
                if word.istitle():
                    return correction.capitalize()
                elif word.isupper():
                    return correction.upper()
                else:
                    return correction
            else:
                candidates = spell.candidates(word.lower())
                suggestions = ", ".join(candidates) if candidates else "No suggestions"
                print(f"Misspelled: '{word}' | Suggestions: {suggestions}")
                return word
        return word

    updated_text = re.sub(r"[\w']+", check_and_replace, text)
    if autofix and misspelled_count > 0:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(updated_text)
            print(f"\nAutofixed {misspelled_count} misspelled word(s) in '{filepath}'.")
        except Exception as e:
            print(f"Error writing to file: {e}")
    elif autofix and misspelled_count == 0:
        print("No misspelled words found to autofix.")
    else:
        if misspelled_count == 0:
            print("No misspelled words found.")
        else:
            print(
                f"\nFound {misspelled_count} misspelled word(s). Run with -a to autofix."
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Detect and optionally autofix misspelled words in a file."
    )
    parser.add_argument("file", help="Path to the text file to check")
    parser.add_argument(
        "-a",
        "--autofix",
        action="store_true",
        help="Automatically correct misspelled words in the file",
    )
    args = parser.parse_args()
    process_file(args.file, args.autofix)
