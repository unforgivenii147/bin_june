#!/data/data/com.termux/files/home/.local/bin/python
"""
Find transliterated Persian words in a dictionary JSON file.
Detects entries where the "translation" is just the English phonetic spelling
of the Persian word rather than an actual translation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from rapidfuzz import fuzz


def is_finglish(text: str, finglish: str) -> int:
    persian_map = {
        "ا": "a",
        "آ": "a",
        "ب": "b",
        "پ": "p",
        "ت": "t",
        "ث": "s",
        "ج": "j",
        "چ": "ch",
        "ح": "h",
        "خ": "kh",
        "د": "d",
        "ذ": "z",
        "ر": "r",
        "ز": "z",
        "ژ": "zh",
        "س": "s",
        "ش": "sh",
        "ص": "s",
        "ض": "z",
        "ط": "t",
        "ظ": "z",
        "ع": "a",
        "غ": "gh",
        "ف": "f",
        "ق": "gh",
        "ک": "k",
        "گ": "g",
        "ل": "l",
        "م": "m",
        "ن": "n",
        "ه": "h",
    }
    words = text.split(" ")
    processed_words = []
    for word in words:
        if not word:
            processed_words.append("")
            continue
        processed_word = ""
        chars = list(word)
        for i, char in enumerate(chars):
            if char == "و":
                if i == 0:
                    processed_word += "v"
                else:
                    processed_word += "o"
            elif char == "ی":
                if i == 0 or i == len(chars) - 1:
                    processed_word += "y"
                else:
                    processed_word += "i"
            else:
                processed_word += persian_map.get(char, char)
        processed_words.append(processed_word)
    result = "".join(processed_words)
    ratio = fuzz.partial_ratio(result, finglish)
    print(f"partial_ratio({result}, {finglish} = {ratio}")
    return ratio >= 60


def is_transliteration(persian_word, english_word):
    if not english_word or not persian_word:
        return False
    return bool(is_finglish(persian_word, english_word))


def find_transliterations(words_dict):
    transliterations = {}
    valid_translations = {}

    for persian_word, english_word in words_dict.items():
        if is_transliteration(persian_word, english_word):
            transliterations[persian_word] = english_word
        else:
            valid_translations[persian_word] = english_word

    return transliterations, valid_translations


def load_json_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{filepath}': {e}")
        sys.exit(1)


def save_json_file(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Find transliterated Persian words in dictionary JSON")
    parser.add_argument("input_file", nargs="?", default="words.json", help="Input JSON file (default: words.json)")
    parser.add_argument(
        "-m", "--move", action="store_true", help="Move found transliterations to errors.json and update words.json"
    )
    parser.add_argument(
        "-e", "--errors-file", default="errors.json", help="Output file for transliterations (default: errors.json)"
    )
    parser.add_argument("-o", "--output", help="Output file for cleaned dictionary (default: overwrite input file)")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output for each transliteration found"
    )

    args = parser.parse_args()

    print(f"Loading dictionary from '{args.input_file}'...")
    words_dict = load_json_file(args.input_file)
    print(f"Loaded {len(words_dict)} entries.")

    print("Analyzing entries for transliterations...")
    transliterations, valid_translations = find_transliterations(words_dict)

    print(f"\nFound {len(transliterations)} potential transliterations:")
    if args.verbose:
        for persian, english in transliterations.items():
            print(f"  {persian}: {english}")
    else:
        for i, (persian, english) in enumerate(transliterations.items()):
            if i < 10:
                print(f"  {persian}: {english}")
            else:
                print(f"  ... and {len(transliterations) - 10} more")
                break

    print(f"Remaining valid translations: {len(valid_translations)}")

    if args.move:
        print(f"\nMoving {len(transliterations)} transliterations to '{args.errors_file}'...")
        save_json_file(transliterations, args.errors_file)

        output_file = args.output if args.output else args.input_file
        print(f"Saving {len(valid_translations)} valid translations to '{output_file}'...")
        save_json_file(valid_translations, output_file)

        print("Done!")
    else:
        print("\nUse -m flag to move these entries to errors.json")
        print(f"Example: python {sys.argv[0]} words.json -m")


if __name__ == "__main__":
    main()
