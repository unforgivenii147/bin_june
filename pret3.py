#!/data/data/com.termux/files/usr/bin/env python
from pathlib import Path
import jsbeautifier


def beautify_file(file_path: Path) -> None:
    content = file_path.read_text(encoding="utf-8")
    if file_path.suffix == ".js":
        beautified_content = jsbeautifier.beautify(content)
    elif file_path.suffix == ".css":
        beautified_content = jsbeautifier.css(content)
    elif file_path.suffix == ".html":
        beautified_content = jsbeautifier.html(content)
    else:
        return
    file_path.write_text(beautified_content, encoding="utf-8")


def beautify_directory(directory: str) -> None:
    base_path = Path(directory)
    for file_path in base_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in (".js", ".css", ".html"):
            print(f"Beautifying: {file_path}")
            beautify_file(file_path)


if __name__ == "__main__":
    beautify_directory(".")
