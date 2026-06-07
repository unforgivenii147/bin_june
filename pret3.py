#!/data/data/com.termux/files/usr/bin/python

import os
from pathlib import Path

import jsbeautifier


def beautify_file(file_path) -> None:
    content = Path(file_path).read_text(encoding="utf-8")
    if file_path.endswith(".js"):
        beautified_content = jsbeautifier.beautify(content)
    elif file_path.endswith(".css"):
        beautified_content = jsbeautifier.css(content)
    elif file_path.endswith(".html"):
        beautified_content = jsbeautifier.html(content)
    else:
        return
    Path(file_path).write_text(beautified_content, encoding="utf-8")


def beautify_directory(directory) -> None:
    for root, _dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith((".js", ".css", ".html")):
                print(f"Beautifying: {file_path}")
                beautify_file(file_path)


if __name__ == "__main__":
    beautify_directory(".")
