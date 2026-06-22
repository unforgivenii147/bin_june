#!/data/data/com.termux/files/usr/bin/python
import pathlib
import pydoc
import sys


def view_file(file_path):
    """Display the contents of a file using pydoc.pager."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        pydoc.pager(content)


def main():
    # Check for recursive flag
    recursive = "-r" in sys.argv

    # Get current directory
    current_dir = pathlib.Path(".")

    # Get all files in the current directory or recursively
    if recursive:
        files = current_dir.rglob("*")  # Recursively find all files
    else:
        files = current_dir.glob("*")  # Find all files in current directory

    # Filter only files (ignore directories)
    files = [f for f in files if f.is_file()]

    # View each file's content
    for file_path in files:
        print(f"Viewing: {file_path}")
        view_file(file_path)


if __name__ == "__main__":
    main()
