#!/data/data/com.termux/files/usr/bin/python

import os
from pathlib import Path
from rcssmin import cssmin
from rjsmin import jsmin


def minify_assets_in_directory(cwd: (Path | str) = ".") -> None:
    minified_count = 0
    errors_count = 0
    for foldername, _subfolders, filenames in os.walk(cwd):
        for filename in filenames:
            file_path = os.path.join(foldername, filename)
            minifier_func = None
            if filename.endswith(".js"):
                minifier_func = jsmin
            elif filename.endswith(".css"):
                minifier_func = cssmin
            else:
                continue
            try:
                print(f"processing ...{Path(file_path).name}")
                original_content = Path(file_path).read_text(encoding="utf-8")
                minified_content = minifier_func(original_content)
                Path(file_path).write_text(minified_content, encoding="utf-8")
                minified_count += 1
            except Exception:
                errors_count += 1


if __name__ == "__main__":
    minify_assets_in_directory(Path.cwd())
