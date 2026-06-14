#!/data/data/com.termux/files/usr/bin/python

import os
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def remove_tag_from_html_file(file_path, tag_name):
    try:
        html = Path(file_path).read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(tag_name):
            tag.decompose()
        Path(file_path).write_text(str(soup), encoding="utf-8")
        print(f"✅ Removed <{tag_name}> from {file_path}")
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")


def process_directory(cwd, tag_name):
    for dirpath, _, filenames in os.walk(cwd):
        for filename in filenames:
            if filename.lower().endswith((".html", ".txt")):
                full_path = os.path.join(dirpath, filename)
                remove_tag_from_html_file(full_path, tag_name)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python remove_tag.py tagname")
        sys.exit(1)
    tag_name = sys.argv[1]
    process_directory(Path.cwd(), tag_name)
