#!/data/data/com.termux/files/usr/bin/python
from pathlib import Path
from joblib import Parallel, delayed
import os
import sys


def is_text_file(file_path):
    """Check if a file is likely a text file by reading a small chunk."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\0" not in chunk  # Binary files often contain null bytes
    except (IOError, PermissionError):
        return False


def search_in_file(file_path, search_string):
    """Search for a string in a file and return matches."""
    try:
        if not is_text_file(file_path):
            return []

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if search_string in content:
                return [str(file_path.relative_to(Path.cwd()))]
    except (IOError, PermissionError, UnicodeDecodeError):
        pass
    return []


def search_in_directory(directory, search_string, n_jobs=-1):
    """Search for a string in all text files in a directory recursively."""
    files = [f for f in directory.rglob("*") if f.is_file()]

    results = Parallel(n_jobs=n_jobs)(delayed(search_in_file)(file, search_string) for file in files)

    matches = [match for sublist in results for match in sublist]
    return matches


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search_for.py <search_string>")
        sys.exit(1)

    search_string = sys.argv[1]
    current_dir = Path.cwd()

    print(f"Searching for '{search_string}' in text files under: {current_dir}")
    matches = search_in_directory(current_dir, search_string)

    if matches:
        print("\nFound in:")
        for match in matches:
            print(match)
    else:
        print("\nNo matches found.")
