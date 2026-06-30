#!/data/data/com.termux/files/usr/bin/python

import io
import os
import re
import tokenize
from pathlib import Path


def remove_comments_and_docstrings(source_code: str) -> str:
    io_obj = io.StringIO(source_code)
    out = ""
    prev_toktype = tokenize.INDENT
    last_lineno = -1
    last_col = 0
    for tok in tokenize.generate_tokens(io_obj.readline):
        toktype = tok[0]
        tok_string = tok[1]
        start_lineno, start_col = tok[2]
        _end_lineno, end_col = tok[3]
        if start_lineno > last_lineno:
            last_col = 0
        if toktype == tokenize.COMMENT or toktype == tokenize.STRING and prev_toktype == tokenize.INDENT:
            pass
        else:
            if start_col > last_col:
                out += " " * (start_col - last_col)
            out += tok_string
            prev_toktype = toktype
            last_col = end_col
            last_lineno = start_lineno
    return out


def shorten_variable_name(name):
    if not name or name.startswith("_"):
        return name
    vowels = "aeiouAEIOU"
    return "".join([char for char in name if char not in vowels])


def compress_python_file_aggressively(filepath: str) -> None:
    content = Path(filepath).read_text(encoding="utf-8")
    content_no_comments = remove_comments_and_docstrings(content)
    lines = content_no_comments.splitlines()
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    content_cleaned = "\n".join(non_empty_lines)
    import keyword

    keywords = set(keyword.kwlist)

    def replacer(match):
        name = match.group(0)
        if name in keywords:
            return name
        return shorten_variable_name(name)

    content_no_multiline_strings = re.sub("'''.*?'''|\\\"\\\"\\\".*?\\\"\\\"\\\"", "", content, flags=re.DOTALL)
    content_no_comments_single = re.sub("#.*", "", content_no_multiline_strings)
    lines = content_no_comments_single.splitlines()
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    final_content = "\n".join(non_empty_lines)
    Path(filepath).write_text(final_content, encoding="utf-8")


def compress_python_files_in_directory(directory: str = ".") -> None:
    for filename in os.listdir(directory):
        if filename.endswith(".py"):
            filepath = os.path.join(directory, filename)
            print(f"Compressing {filepath} (removing comments, docstrings, whitespace)...")
            compress_python_file_aggressively(filepath)
    print("Compression complete.")


if __name__ == "__main__":
    print("WARNING: This script will modify your Python files by removing comments,")
    print("docstrings, and whitespace. It DOES NOT perform aggressive variable renaming")
    print("due to the high risk of breaking code and reducing AI understandability.")
    print("Please ensure you have backups before proceeding.")
    print(
        """
Script finished. No files were modified by default. Uncomment 'compress_python_files_in_directory('.')' to run."""
    )
