#!/data/data/com.termux/files/usr/bin/env python

"""Module for rename_html_by_title.py."""

from __future__ import annotations

import re
import unicodedata
from collections import deque
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


def finglish(text: str) -> str:
    persian_map = {
        "ا": "a",
        "آ": "a",
        "ب": "b",
        "پ": "p",
        "ت": "t",
        "ث": "s",
        "ج": "j",
        "چ": "ch",
        "ح": "h",
        "خ": "kh",
        "د": "d",
        "ذ": "z",
        "ر": "r",
        "ز": "z",
        "ژ": "zh",
        "س": "s",
        "ش": "sh",
        "ص": "s",
        "ض": "z",
        "ط": "t",
        "ظ": "z",
        "ع": "a",
        "غ": "gh",
        "ف": "f",
        "ق": "gh",
        "ک": "k",
        "گ": "g",
        "ل": "l",
        "م": "m",
        "ن": "n",
        "ه": "h",
    }
    words = text.split(" ")
    processed_words = []
    for word in words:
        if not word:
            processed_words.append("")
            continue
        processed_word = ""
        chars = list(word)
        for i, char in enumerate(chars):
            if char == "و":
                if i == 0:
                    processed_word += "v"
                else:
                    processed_word += "o"
            elif char == "ی":
                if i == 0 or i == len(chars) - 1:
                    processed_word += "y"
                else:
                    processed_word += "i"
            else:
                processed_word += persian_map.get(char, char)
        processed_words.append(processed_word)
    return " ".join(processed_words)


class TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title = None

    def handle_starttag(self, tag, attrs) -> None:
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data) -> None:
        if self.in_title and self.title is None:
            self.title = data.strip()


def extract_title(html_path: Path) -> str | None:
    try:
        parser = TitleParser()
        parser.feed(html_path.read_text(encoding="utf-8", errors="ignore"))
        return parser.title
    except Exception:
        return None


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    temp = text
    text = text.lower()
    text = re.sub(
        "(\\?|\\|\\||\\`|\\<|\\>|\\~|\\:|\\;|\\\"|'|\\@|\\$|\\#|\\%|\\&|\\^|\\(|\\)|\\{|\\}|\\[|\\])",
        "",
        text,
    )
    text = re.sub("( )+", "_", text)
    text = re.sub("(/)+", "_", text)
    text = re.sub("(__)+", "_", text)
    if len(text) < 2:
        return temp.replace(":", "").replace("?", "").replace("=", "")
    return text


def unique_path(path: Path) -> Path:
    counter = 1
    new_path = path
    while new_path.exists():
        new_path = path.with_stem(f"{path.stem}-{counter}")
        counter += 1
    return new_path


def process_file(path: str | Path) -> None:
    path = Path(path)
    title = extract_title(path)
    if not title:
        return
    slug = slugify(title)
    if not slug:
        return
    name = finglish(slug)
    new_path = path.with_name(name + path.suffix)
    if new_path.exists():
        new_path = unique_path(new_path)
    if path == new_path:
        return
    print(f"{path.name[:10]} -> {new_path.name[:25]}")
    path.rename(new_path)


if __name__ == "__main__":
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".html"])
    mpf3(process_file, files)
