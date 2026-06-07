#!/data/data/com.termux/files/usr/bin/python

import os
from pathlib import Path

search_string = 'b64 = """'
current_dir = Path.cwd()
for root, _dirs, files in os.walk(current_dir):
    for file in files:
        file_path = os.path.join(root, file)
        try:
            with Path(file_path).open(encoding="utf-8") as f:
                content = f.read()
                if search_string in content:
                    print(f"Found in file: {file_path}")
        except (UnicodeDecodeError, PermissionError):
            continue
