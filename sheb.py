#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import os
from pathlib import Path
from dh.fileutils import is_python_file

TARGET_SHEBANG = "#!/data/data/com.termux/files/usr/bin/env python"


def process_file(filepath) -> None:
    Path(path)
    with Path(filepath).open("r+", encoding="utf-8") as f:
        lines = f.readlines()
        if not lines:
            return
        if lines and lines[0].startswith("#!"):
            lines[0] = TARGET_SHEBANG + "\n"
            if len(lines) > 1 and lines[1].strip():
                lines.insert(1, "\n")
        else:
            has_python_code = any(line.strip().startswith(("import ", "from ", "def ", "class ")) for line in lines)
            if has_python_code:
                lines.insert(0, TARGET_SHEBANG + "\n")
                lines.insert(1, "\n")
        f.seek(0)
        f.writelines(lines)
        f.truncate()
        print(f"{os.path.relpath(filepath)} updated.")
    if "bin" in filepath.split(os.sep):
        Path(filepath).chmod(0o755)


def traverse_directory(directory: Path) -> None:
    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            if Path(filepath).is_symlink():
                continue
            if is_python_file(filepath):
                process_file(filepath)


if __name__ == "__main__":
    traverse_directory(Path.cwd())
