#!/data/data/com.termux/files/usr/bin/python

import os
import re
from pathlib import Path

static_dir = "/sdcard/_static"


def fix_links(file_path: Path):
    content: str = file_path.read_text(encoding="utf-8", errors="replace")
    links = re.findall("href=[\\'\"]?([^\\'\" >]+)", content)
    for link in links:
        if not Path(link).exists():
            static_file = static_dir / link
            if static_file.exists():
                content = content.replace(link, str(static_file.resolve()))
    backup_path = file_path.with_suffix(".bak")
    Path(file_path).replace(backup_path)
    Path(file_path).write_text(content, encoding="utf-8")


def main():
    for root, _dirs, files in os.walk("."):
        for file in files:
            if file.endswith((".md", ".html")):
                file_path = Path(root) / file
                fix_links(file_path)


if __name__ == "__main__":
    main()
