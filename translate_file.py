#!/data/data/com.termux/files/usr/bin/env python


from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from deep_translator import GoogleTranslator
import re

LANGUAGE_PATTERN = re.compile(
    "[\\u0600-\\u06FF\\u4E00-\\u9FFF\\u3040-\\u309F\\u30A0-\\u30FF\\uAC00-\\uD7AF\\u0400-\\u04FF]"
)


def is_foreign_line(line):
    return bool(LANGUAGE_PATTERN.search(line))


def process_file(file_path):
    try:
        translator = GoogleTranslator(source="auto", target="en")
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        modified = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and is_foreign_line(stripped):
                try:
                    translated = translator.translate(stripped)
                    indent = line[: len(line) - len(line.lstrip())]
                    new_lines.append(f"{indent}{translated}\n")
                    modified = True
                except Exception as e:
                    print(f"Error translating line in {file_path}: {e}")
                    new_lines.append(line)
            else:
                new_lines.append(line)
        if modified:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return f"Updated: {file_path}"
        return f"No changes needed: {file_path}"
    except Exception as e:
        return f"Error processing {file_path}: {e}"


def main():
    extensions = ["*.txt", "*.md", "*.py", "*.json", "*.csv"]
    files_to_process = []
    for ext in extensions:
        files_to_process.extend(Path(".").rglob(ext))
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_file, files_to_process))
    for result in results:
        print(result)


if __name__ == "__main__":
    main()
