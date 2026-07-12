#!/data/data/com.termux/files/usr/bin/env python


import unicodedata
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def custom_persian_to_finglish(text: str) -> str:
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
    return " ".join(processed_words)


def convert_filenames_with_pathlib(directory: str = ".") -> None:
    start_path = Path(directory)
    for filepath in start_path.rglob("*"):
        original_filename_stem = filepath.stem
        original_extension = filepath.suffix
        normalized_stem = unicodedata.normalize("NFKD", original_filename_stem)
        finglish_stem = custom_persian_to_finglish(normalized_stem)
        finglish_stem_cleaned = "_".join(filter(None, finglish_stem.split("_")))
        new_filename = finglish_stem_cleaned + original_extension
        if new_filename != filepath.name:
            new_filepath = filepath.with_name(new_filename)
            try:
                filepath.rename(new_filepath)
                print(f"Renamed: {filepath} -> {new_filepath}")
            except OSError as e:
                print(f"Error renaming {filepath}: {e}")


if __name__ == "__main__":
    convert_filenames_with_pathlib()
