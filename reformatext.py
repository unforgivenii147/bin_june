#!/data/data/com.termux/files/usr/bin/env python

"""Module for reformatext.py."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def restructure_text_file(filepath: Path) -> None:
    if not filepath.is_file():
        print(f"Error: File not found at {filepath}")
        return
    try:
        with filepath.open("r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return
    bak_filepath = filepath.with_suffix(filepath.suffix + ".bak")
    try:
        with (
            filepath.open("r", encoding="utf-8") as src,
            bak_filepath.open("w", encoding="utf-8") as dst,
        ):
            dst.write(src.read())
        print(f"Backup created at: {bak_filepath}")
    except Exception as e:
        print(f"Error creating backup file {bak_filepath}: {e}")
        return
    restructured_lines = []
    paragraphs = content.split("\n\n")
    for paragraph in paragraphs:
        if not paragraph.strip():
            restructured_lines.append("")
            continue
        sentences = re.split(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s+", paragraph)
        for sentence in sentences:
            if not sentence.strip():
                continue
            processed_sentence_parts = []
            current_line_length = 0
            words = sentence.split()
            current_line_words = []
            for word in words:
                potential_line_length = current_line_length + len(word) + (1 if current_line_words else 0)
                if potential_line_length > 120 and current_line_length > 0:
                    break_point = -1
                    for i, w in enumerate(current_line_words):
                        if w.endswith(","):
                            break_point = i
                    if break_point != -1:
                        processed_sentence_parts.append(" ".join(current_line_words[: break_point + 1]))
                        current_line_words = current_line_words[break_point + 1 :]
                        current_line_length = len(" ".join(current_line_words))
                    else:
                        processed_sentence_parts.append(" ".join(current_line_words))
                        current_line_words = [word]
                        current_line_length = len(word)
                else:
                    current_line_words.append(word)
                    current_line_length = potential_line_length
            if current_line_words:
                processed_sentence_parts.append(" ".join(current_line_words))
            restructured_lines.extend(processed_sentence_parts)
    try:
        with filepath.open("w", encoding="utf-8") as f:
            f.write("\n".join(restructured_lines))
        print(f"File successfully restructured: {filepath}")
    except Exception as e:
        print(f"Error writing to file {filepath}: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <filename>")
        sys.exit(1)
    filename = sys.argv[1]
    file_path = Path(filename)
    restructure_text_file(file_path)
