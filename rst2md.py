#!/data/data/com.termux/files/usr/bin/python


"""
Convert .rst files to .md in-place.
Usage: python rst_to_md.py file1.rst file2.rst ...
       python rst_to_md.py --recursive directory/
"""

import os
import sys
import argparse
from pathlib import Path

try:
    from docutils.core import publish_parts
except ImportError:
    print("Error: docutils is required. Install with: pip install docutils")
    sys.exit(1)
try:
    from mistletoe import markdown as mistletoe_markdown
    from mistletoe.html_renderer import HTMLRenderer
except ImportError:
    print("Error: mistletoe is required. Install with: pip install mistletoe")
    sys.exit(1)


def rst_to_markdown(content):
    try:
        parts = publish_parts(
            source=content,
            writer_name="html",
            settings_overrides={"initial_header_level": 2, "warning_stream": None, "report_level": 5},
        )
        html_content = parts["html_body"]
        from mistletoe import Document
        from mistletoe.html_tokenizer import tokenize_html

        tokens = tokenize_html(html_content)
        markdown_content = ""
        with HTMLRenderer() as renderer:
            document = Document(tokens)
            markdown_content = renderer.render(document)
        return markdown_content
    except Exception as e:
        print(f"Conversion error details: {e}")
        raise


def convert_file(filepath, backup=True, remove_original=False):
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return False
    if filepath.suffix.lower() != ".rst":
        print(f"Skipping {filepath}: not an .rst file")
        return False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            rst_content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False
    try:
        markdown_content = rst_to_markdown(rst_content)
    except Exception as e:
        print(f"Error converting {filepath}: {e}")
        return False
    if backup:
        backup_path = filepath.with_suffix(".rst.bak")
        try:
            import shutil

            shutil.copy2(filepath, backup_path)
            print(f"Backup created: {backup_path}")
        except Exception as e:
            print(f"Warning: could not create backup: {e}")
    md_path = filepath.with_suffix(".md")
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        if remove_original:
            filepath.unlink()
            print(f"Converted and removed original: {filepath} -> {md_path}")
        else:
            print(f"Converted: {filepath} -> {md_path}")
        return True
    except Exception as e:
        print(f"Error writing {md_path}: {e}")
        return False


def convert_recursive(directory, backup=True, remove_original=False):
    directory = Path(directory)
    if not directory.exists():
        print(f"Error: {directory} not found")
        return
    rst_files = list(directory.rglob("*.rst"))
    if not rst_files:
        print(f"No .rst files found in {directory}")
        return
    print(f"Found {len(rst_files)} .rst files")
    success_count = 0
    for rst_file in rst_files:
        if convert_file(rst_file, backup, remove_original):
            success_count += 1
    print(f"\nConverted {success_count}/{len(rst_files)} files")


def main():
    parser = argparse.ArgumentParser(
        description="Convert .rst files to .md in-place",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\nExamples:\n  python rst_to_md.py file1.rst file2.rst\n  python rst_to_md.py --recursive docs/\n  python rst_to_md.py --no-backup file.rst\n  python rst_to_md.py --remove-original file.rst\n        ",
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to convert")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively process directories")
    parser.add_argument("--no-backup", action="store_true", help="Do not create backup files")
    parser.add_argument("--remove-original", action="store_true", help="Remove original .rst files after conversion")
    args = parser.parse_args()
    backup = not args.no_backup
    for path in args.paths:
        path_obj = Path(path)
        if path_obj.is_dir():
            if args.recursive:
                convert_recursive(path_obj, backup, args.remove_original)
            else:
                print(f"Skipping directory {path}. Use --recursive to process directories.")
        elif path_obj.is_file():
            convert_file(path_obj, backup, args.remove_original)
        else:
            print(f"Error: {path} is not a valid file or directory")


if __name__ == "__main__":
    main()
