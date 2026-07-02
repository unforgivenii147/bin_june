#!/data/data/com.termux/files/usr/bin/env python
"""
Convert CodePen-style HTML (body only) to a complete HTML document.
Adds proper <head> section with links to style.css and script.js
"""

import os
import sys
from pathlib import Path


def convert_codepen_html(html_content, title="Document", charset="UTF-8"):
    """
    Convert CodePen-style HTML to a full valid HTML document.

    Args:
        html_content (str): The body HTML content from CodePen
        title (str): The title for the HTML document (default: "Document")
        charset (str): Character encoding (default: "UTF-8")

    Returns:
        str: Complete HTML document
    """
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="{charset}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
{html_content}
    <script src="script.js"></script>
</body>
</html>
"""
    return full_html


def process_file(input_file, output_file=None, title=None):
    """
    Process an HTML file and save the converted output.

    Args:
        input_file (str): Path to input HTML file
        output_file (str): Path to output HTML file (default: input_file)
        title (str): Title for the HTML document
    """
    # Read the input file
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
        return False
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

    # Use input filename as title if not provided
    if title is None:
        title = Path(input_file).stem.replace("-", " ").title()

    # Convert the HTML
    full_html = convert_codepen_html(html_content, title)

    # Determine output file
    if output_file is None:
        output_file = input_file

    # Write the output file
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"✓ Successfully converted: {input_file}")
        print(f"✓ Saved to: {output_file}")
        return True
    except Exception as e:
        print(f"Error writing file: {e}")
        return False


def main():
    """
    Command-line interface for the converter.
    Usage: python script.py <input_file> [output_file] [--title "Page Title"]
    """
    if len(sys.argv) < 2:
        print("Usage: python codepen_converter.py <input_file> [output_file] [--title 'Page Title']")
        print("\nExample:")
        print("  python codepen_converter.py index.html")
        print("  python codepen_converter.py codepen.html output.html")
        print("  python codepen_converter.py codepen.html --title 'My Project'")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = None
    title = None

    # Parse additional arguments
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--title" and i + 1 < len(sys.argv):
            title = sys.argv[i + 1]
            i += 2
        else:
            output_file = sys.argv[i]
            i += 1

    # Process the file
    success = process_file(input_file, output_file, title)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
