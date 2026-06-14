#!/data/data/com.termux/files/usr/bin/python

import os
import re
from pathlib import Path

OUTPUT_DIR = Path("output")
if not OUTPUT_DIR.exists():
    OUTPUT_DIR.mkdir(exist_ok=True)


def extract_code_snippets_with_details(markdown_content: str):
    snippets_data = []
    lines = markdown_content.splitlines()
    in_code_block = False
    current_block_lines = []
    start_line_num = -1
    language = ""
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            if in_code_block:
                snippets_data.append({
                    "language": language,
                    "start_line": start_line_num,
                    "end_line": i,
                    "content": "\n".join(current_block_lines),
                })
                in_code_block = False
                current_block_lines = []
                language = ""
            else:
                in_code_block = True
                start_line_num = i + 1
                match = re.match("```(\\w*)", line.strip())
                language = match.group(1).lower() if match and match.group(1) else ""
                current_block_lines = []
        elif in_code_block:
            current_block_lines.append(line)
    if in_code_block:
        snippets_data.append({
            "language": language,
            "start_line": start_line_num,
            "end_line": len(lines),
            "content": "\n".join(current_block_lines),
        })
    return snippets_data


def get_extension_from_language(language) -> str:
    extensions = {
        "sh": ".sh",
        "bash": ".sh",
        "zsh": ".sh",
        "python": ".py",
        "py": ".py",
        "javascript": ".js",
        "js": ".js",
        "html": ".html",
        "css": ".css",
        "json": ".json",
        "yaml": ".yaml",
        "yml": ".yaml",
        "sql": ".sql",
        "md": ".md",
        "text": ".txt",
        "plain": ".txt",
        "": ".txt",
    }
    return extensions.get(language.lower(), ".txt")


def process_markdown_files(directory: str = ".") -> None:
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith((".md", ".markdown", ".metadata", "METADATA", "PKGINFO", "PKG-INFO")):
                filepath = os.path.join(root, file)
                try:
                    content = Path(filepath).read_text(encoding="utf-8")
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
                    continue
                code_details = extract_code_snippets_with_details(content)
                if code_details:
                    base_name = os.path.splitext(file)[0]
                    for _i, details in enumerate(code_details):
                        line_range = f"{details['start_line']}-{details['end_line']}"
                        language = details["language"]
                        extension = get_extension_from_language(language)
                        output_filename = f"output/{base_name}_lines_{line_range}{extension}"
                        output_path = os.path.join(root, output_filename)
                        Path(output_path).write_text(details["content"].strip(), encoding="utf-8")
                        print(
                            f"Saved snippet from {filepath} (Lines {line_range}, Lang: '{language}') to {output_path}"
                        )


if __name__ == "__main__":
    process_markdown_files()
