#!/data/data/com.termux/files/usr/bin/python

import datetime
import json
import os
from pathlib import Path

INFO_PATH = Path("~/isaac/.info.json").expanduser()


def load_user_info() -> dict:
    with Path(INFO_PATH).open(encoding="utf-8") as f:
        return json.load(f)


def is_python_file(path: str) -> bool:
    if Path(path).is_dir():
        return False
    if path.endswith(".py"):
        return True
    try:
        with Path(path).open(encoding="utf-8", errors="ignore") as f:
            first_line = f.readline().strip()
            if first_line.startswith("#!"):
                return "python" in first_line
            sample = f.read(200)
            return any((tok in sample for tok in ("def ", "class ", "import ", "from ")))
    except Exception:
        return False


def build_header(info: dict) -> str:
    now = datetime.datetime.now()
    timestamp = now.strftime("%a %d %b %Y | %H:%M:%S")
    return f"# Author : {info.get('name', '')}\n# Email  : {info.get('email', '')}\n# Time   : {timestamp}\n\n\n"


def file_already_has_header(contents: str) -> bool:
    return "# Author :" in contents.split("\n")[:5]


def process_file(path: str, header: str) -> None:
    with Path(path).open(encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    if file_already_has_header("".join(lines)):
        return
    if lines and lines[0].startswith("#!"):
        new_contents = lines[0] + header + "".join(lines[1:])
    else:
        new_contents = header + "".join(lines)
    Path(path).write_text(new_contents, encoding="utf-8")


def main() -> None:
    info = load_user_info()
    header = build_header(info)
    for root, _, files in os.walk("."):
        for fn in files:
            path = os.path.join(root, fn)
            if is_python_file(path):
                process_file(path, header)


if __name__ == "__main__":
    main()
