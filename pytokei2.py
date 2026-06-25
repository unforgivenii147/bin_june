#!/data/data/com.termux/files/usr/bin/python

import os
import re


def count_lines_of_code(file_path: str, lang) -> tuple[int, int, int]:
    if ".git" in str(file_path):
        return (0, 0, 0)
    if is_binary(file_path):
        print(f"{file_path} is binary")
        return (0, 0, 0)
    with Path(file_path).open(encoding="utf-8") as file:
        code_lines = 0
        comment_lines = 0
        blank_lines = 0
        for line in file:
            if not line.strip():
                blank_lines += 1
            elif re.match(COMMENT_PATTERNS.get(lang, ""), line):
                comment_lines += 1
            else:
                code_lines += 1
    return (code_lines, comment_lines, blank_lines)


def scan_directory(directory: str = "."):
    stats = {
        "total": {"code": 0, "comments": 0, "blank": 0},
        "languages": {lang: {"code": 0, "comments": 0, "blank": 0} for lang in LANG_EXTENSIONS},
    }
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            file_extension = os.path.splitext(file)[1].lower()
            if not file_extension:
                lang = get_language_from_shebang(file_path)
                if lang:
                    code, comments, blanks = count_lines_of_code(file_path, lang)
                    stats["languages"][lang]["code"] += code
                    stats["languages"][lang]["comments"] += comments
                    stats["languages"][lang]["blank"] += blanks
                    stats["total"]["code"] += code
                    stats["total"]["comments"] += comments
                    stats["total"]["blank"] += blanks
                    continue
            for lang, extensions in LANG_EXTENSIONS.items():
                if file_extension in extensions:
                    code, comments, blanks = count_lines_of_code(file_path, lang)
                    stats["languages"][lang]["code"] += code
                    stats["languages"][lang]["comments"] += comments
                    stats["languages"][lang]["blank"] += blanks
                    stats["total"]["code"] += code
                    stats["total"]["comments"] += comments
                    stats["total"]["blank"] += blanks
                    break
    return stats


def display_stats(stats) -> None:
    for lang_stats in stats["languages"].values():
        lang_stats["code"] > 0


if __name__ == "__main__":
    stats = scan_directory()
    display_stats(stats)
