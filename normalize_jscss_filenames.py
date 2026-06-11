#!/data/data/com.termux/files/usr/bin/python
import re
import os
from pathlib import Path


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


def normalize_file_contents(filepath, output_path=None):
    """
    Read a file, normalize JS/CSS references in its content, and save it

    Args:
        filepath (str): Path to input file
        output_path (str, optional): Path to output file. If None, overwrites original
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    normalized_content = normalize_filenames_in_text(content)

    output_file = output_path if output_path else filepath
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(normalized_content)

    print(f"Processed: {filepath} -> {output_file}")


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
                filepath = os.path.join(root, file)
                try:
                    normalize_file_contents(filepath)
                    processed_count += 1
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

    print(f"\nProcessed {processed_count} files")


# Examples and usage
if __name__ == "__main__":
    # Example 1: Normalize individual filenames
    test_filenames = [
        "script.js?version=3.6.6",
        "style.css?v=2.0.1",
        "main.js#hash123",
        "bundle.min.js?cache_buster=12345",
        "theme.css?ver=4.7.2",
        "normal.js",
        "style.min.css",
        "app.js?param1=value1&param2=value2",
    ]

    print("=== Single Filename Normalization ===\n")
    for filename in test_filenames:
        normalized = normalize_filename(filename)
        print(f"Original: {filename:40} -> Normalized: {normalized}")

    # Example 2: Normalize filenames within text/html content
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="style.css?version=3.6.6">
        <script src="main.js?v=2.0"></script>
        <link rel="stylesheet" href="theme.min.css?ver=1.2.3">
    </head>
    <body>
        <script src="bundle.js?cache_buster=12345"></script>
    </body>
    </html>
    """

    print("\n\n=== HTML Content Normalization ===\n")
    print("Original HTML:")
    print(html_content)
    print("\nNormalized HTML:")
    print(normalize_filenames_in_text(html_content))

    # Example 3: Process a directory (uncomment and modify path to use)
    # print("\n\n=== Batch Processing ===\n")
    # normalize_filenames_batch("/path/to/your/project")

    # Example 4: Single file processing (uncomment to use)
    # print("\n\n=== Single File Processing ===\n")
    # normalize_file_contents("index.html", "index_normalized.html")
