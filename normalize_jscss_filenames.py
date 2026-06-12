#!/data/data/com.termux/files/usr/bin/python
import os
import re
from pathlib import Path

from dh import unique_path


def normalize_filename(filename):
    """
    Normalize JS and CSS filenames by removing everything after .js or .css

    Args:
        filename (str): Original filename

    Returns:
        str: Normalized filename
    """
    # Pattern to match .js or .css followed by anything except alphanumeric, dot, dash, underscore
    # This handles cases like: script.js?version=1.2.3, style.css?v=2.0, main.js#hash
    pattern = r"(\.(?:js|css))([?#].*)?$"

    # Replace with just the extension
    normalized = re.sub(pattern, r"\1", filename, flags=re.IGNORECASE)

    return normalized


def normalize_filenames_in_text(text):
    """
    Find and normalize all JS/CSS filenames in a text string

    Args:
        text (str): Text containing file references

    Returns:
        str: Text with normalized filenames
    """
    # Pattern to match URLs/paths ending with .js or .css followed by query/hash
    # This matches words that end with .js?..., .css?..., .js#..., etc.
    pattern = r'\b([^\s<>"\']*?\.(?:js|css))([?#][^\s<>"\']*)?\b'

    def replace_match(match):
        return match.group(1)  # Return only the base filename with extension

    normalized_text = re.sub(pattern, replace_match, text, flags=re.IGNORECASE)
    return normalized_text


def normalize_file_contents(path):
    """
    Read a file, normalize JS/CSS references in its content, and save it

    Args:
        path (str): Path to input file
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    normalized_content = normalize_filenames_in_text(content)

    with open(path, "w", encoding="utf-8") as f:
        f.write(normalized_content)

    print(f"Processed: {path}")


def normalize_filenames_batch(directory, file_extensions=None):
    """
    Process all HTML, PHP, JS, etc. files in a directory

    Args:
        directory (str): Directory to scan
        file_extensions (list): File extensions to process (default: .html, .htm, .php, .js, .css)
    """
    if file_extensions is None:
        file_extensions = [".html", ".htm", ".php", ".js", ".css", ".xml", ".json"]

    processed_count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in file_extensions):
                path = Path(root) / file
                try:
                    new_name = normalize_filename(file)
                    new_path = path.with_name(new_name)
                    if new_path.exists():
                        new_path = unique_path(new_path)
                    path.rename(new_path)
                    processed_count += 1
                except Exception as e:
                    print(f"Error processing {path}: {e}")

    print(f"\nProcessed {processed_count} files")


# Examples and usage
if __name__ == "__main__":
    cwd = Path.cwd()
    normalize_filenames_batch(cwd)

    # normalize_file_contents("index.html", "index_normalized.html")
