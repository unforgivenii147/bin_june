#!/data/data/com.termux/files/usr/bin/env python

from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def create_html_template(filename: str = "index.html") -> None:
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>
<body>
    <h1>Hello, World!</h1>
    <!-- Your content here -->
</body>
</html>
"""
    try:
        Path(filename).write_text(html_template, encoding="utf-8")
        print(f"Successfully created {filename} in {Path.cwd()}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    create_html_template()
