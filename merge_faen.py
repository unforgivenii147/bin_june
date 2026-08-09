#!/data/data/com.termux/files/home/.local/bin/python
import sys
import json


def main():
    if len(sys.argv) < 3:
        print("Usage: python script.py <english_file> <persian_file>")
        sys.exit(1)

    english_file = sys.argv[1]
    persian_file = sys.argv[2]

    # Read both files
    with open(english_file, "r", encoding="utf-8") as f:
        english_words = [line.strip() for line in f if line.strip()]

    with open(persian_file, "r", encoding="utf-8") as f:
        persian_words = [line.strip() for line in f if line.strip()]

    # Verify matching counts
    if len(english_words) != len(persian_words):
        print(f"Warning: word count mismatch ({len(english_words)} vs {len(persian_words)})")

    # Create list of dictionaries
    dictionary = [{en: fa} for en, fa in zip(english_words, persian_words)]

    # Save to dic.json
    with open("dic.json", "w", encoding="utf-8") as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2)

    print(f"✓ Dictionary saved: {len(dictionary)} entries")


if __name__ == "__main__":
    main()
