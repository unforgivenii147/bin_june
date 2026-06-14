#!/data/data/com.termux/files/usr/bin/python

import json
import os
from pathlib import Path

import jsbeautifier


def beautify_json_file(file_path: str) -> bool | None:
    try:
        with Path(file_path).open(encoding="utf-8") as f:
            data = json.load(f)
        with Path(file_path).open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except json.JSONDecodeError:
        return False
    except Exception:
        return False


def beautify_code_file(file_path: str, beautify_function, asset_type: str) -> bool | None:
    try:
        original_content = Path(file_path).read_text(encoding="utf-8")
        options = jsbeautifier.default_options()
        options.indent_size = 4
        beautified_content = beautify_function(original_content, options)
        Path(file_path).write_text(beautified_content, encoding="utf-8")
        return True
    except Exception:
        return False


def beautify_files_in_directory(cwd: Path | str = ".") -> None:
    processed_count = 0
    errors_count = 0
    beautifier_map = {
        ".js": (jsbeautifier.beautify, "JS"),
        ".html": (jsbeautifier.beautify, "HTML"),
        ".css": (jsbeautifier.beautify, "CSS"),
    }
    for foldername, _subfolders, filenames in os.walk(cwd):
        for filename in filenames:
            file_path = os.path.join(foldername, filename)
            if filename.endswith(".json"):
                success = beautify_json_file(file_path)
                if success:
                    processed_count += 1
                else:
                    errors_count += 1
            for ext, (func, asset_type) in beautifier_map.items():
                if filename.endswith(ext):
                    success = beautify_code_file(file_path, func, asset_type)
                    if success:
                        processed_count += 1
                    else:
                        errors_count += 1
                    break


if __name__ == "__main__":
    beautify_files_in_directory(Path.cwd())
