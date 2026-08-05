#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys


def persian_sort_key(word):
    """
    Create a sort key for Persian words.
    Persian alphabet order:
    ا, ب, پ, ت, ث, ج, چ, ح, خ, د, ذ, ر, ز, ژ, س, ش, ص, ض, ط, ظ, ع, غ, ف, ق, ک, گ, ل, م, ن, و, ه, ی
    """

    persian_order = {
        "آ": "ا",
        "ا": "ا",
        "ب": "ب",
        "پ": "پ",
        "ت": "ت",
        "ث": "ث",
        "ج": "ج",
        "چ": "چ",
        "ح": "ح",
        "خ": "خ",
        "د": "د",
        "ذ": "ذ",
        "ر": "ر",
        "ز": "ز",
        "ژ": "ژ",
        "س": "س",
        "ش": "ش",
        "ص": "ص",
        "ض": "ض",
        "ط": "ط",
        "ظ": "ظ",
        "ع": "ع",
        "غ": "غ",
        "ف": "ف",
        "ق": "ق",
        "ک": "ک",
        "گ": "گ",
        "ل": "ل",
        "م": "م",
        "ن": "ن",
        "و": "و",
        "ه": "ه",
        "ة": "ه",
        "ی": "ی",
        "ي": "ی",
        "ئ": "ی",
        " ": " ",
    }

    custom_order = [
        "ا",
        "ب",
        "پ",
        "ت",
        "ث",
        "ج",
        "چ",
        "ح",
        "خ",
        "د",
        "ذ",
        "ر",
        "ز",
        "ژ",
        "س",
        "ش",
        "ص",
        "ض",
        "ط",
        "ظ",
        "ع",
        "غ",
        "ف",
        "ق",
        "ک",
        "گ",
        "ل",
        "م",
        "ن",
        "و",
        "ه",
        "ی",
    ]

    char_rank = {char: i for i, char in enumerate(custom_order)}

    sort_key = []
    for char in word:
        mapped_char = persian_order.get(char, char)

        rank = char_rank.get(mapped_char, len(custom_order))
        sort_key.append(rank)

    return tuple(sort_key)


def sort_persian_dict(file_path):
    """
    Sort a Persian dictionary file in place.
    Each line contains one word.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        words = [line.rstrip("\n\r") for line in lines]

        sorted_words = sorted(words, key=lambda w: (persian_sort_key(w), w))

        with open(file_path, "w", encoding="utf-8") as f:
            for word in sorted_words:
                f.write(word + "\n")

        print(f"Successfully sorted {len(sorted_words)} words in '{file_path}'")

    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python persian_sort.py <filename>")
        sys.exit(1)

    file_path = sys.argv[1]
    sort_persian_dict(file_path)
