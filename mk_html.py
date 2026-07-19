#!/data/data/com.termux/files/usr/bin/env python
from __future__ import absolute_import

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Configuration
RST2HTML_OPTIONS = " ".join(["--no-toc-backlinks", "--strip-comments", "--language en", "--date"])

# File extensions to process
VALID_EXTENSIONS = {".rst", ".txt", ".md"}

# Compiled regex patterns
MD_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MD_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
MD_CODE_BLOCK_PATTERN = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)


def find_rst2html_script():
    """Find the rest2html.py script in common locations."""
    possible_paths = [
        Path.cwd() / "doc" / "rest2html.py",
        Path.cwd() / "rest2html.py",
        Path(sys.prefix) / "doc" / "rest2html.py",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    return None


def convert_md_to_rst(content: str) -> str:
    """Convert Markdown content to reStructuredText."""

    # Convert headings
    def replace_heading(match):
        level = len(match.group(1))
        text = match.group(2).strip()
        if level == 1:
            return f"{'=' * len(text)}\n{text}\n{'=' * len(text)}"
        elif level == 2:
            return f"{text}\n{'-' * len(text)}"
        else:
            char = "~^+"[min(level - 3, 2)]
            return f"{text}\n{char * len(text)}"

    content = MD_HEADING_PATTERN.sub(replace_heading, content)

    # Convert links
    content = MD_LINK_PATTERN.sub(r"`\1 <\2>`_", content)

    # Convert code blocks
    def replace_code_block(match):
        language = match.group(1)
        code = match.group(2).strip()
        if language:
            return f".. code-block:: {language}\n\n    {chr(10).join('    ' + line for line in code.split(chr(10)))}\n"
        else:
            return f"::\n\n    {chr(10).join('    ' + line for line in code.split(chr(10)))}\n"

    content = MD_CODE_BLOCK_PATTERN.sub(replace_code_block, content)

    # Convert bold and italic
    content = re.sub(r"\*\*(.+?)\*\*", r"**\1**", content)
    content = re.sub(r"\*(.+?)\*", r"*\1*", content)

    # Convert inline code
    content = re.sub(r"`([^`]+)`", r"``\1``", content)

    # Convert horizontal rules
    content = re.sub(r"^---$", "-------", content, flags=re.MULTILINE)

    # Convert unordered lists
    content = re.sub(r"^\* ", r"- ", content, flags=re.MULTILINE)

    return content


def convert_file_to_html(file_path: Path, stylesheet_url: str = None) -> Path:
    """Convert a single file to HTML using appropriate converter."""
    try:
        html_path = file_path.with_suffix(".html")

        # Skip if HTML is newer than source
        if html_path.exists() and html_path.stat().st_mtime > file_path.stat().st_mtime:
            return html_path

        content = file_path.read_text(encoding="utf-8")

        # Convert MD to RST first if needed
        if file_path.suffix.lower() == ".md":
            content = convert_md_to_rst(content)
            temp_file = file_path.with_suffix(".rst")
            temp_file.write_text(content, encoding="utf-8")
            file_path = temp_file
            cleanup_temp = True
        else:
            cleanup_temp = False

        # Build the conversion command
        cmd = [
            sys.executable,
            "-m",
            "docutils.__main__",
            file_path,
            html_path,
        ]

        if stylesheet_url:
            cmd.extend(["--stylesheet", stylesheet_url, "--link-stylesheet"])

        # Try docutils first, fall back to rst2html script
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fall back to custom rst2html script
            rst2html_script = find_rst2html_script()
            if rst2html_script:
                cmd = [
                    sys.executable,
                    str(rst2html_script),
                ] + RST2HTML_OPTIONS.split()

                if stylesheet_url:
                    cmd.extend(["--stylesheet", stylesheet_url, "--link-stylesheet"])

                cmd.extend([str(file_path), str(html_path)])

                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            else:
                raise RuntimeError("No RST to HTML converter found")

        # Clean up temporary file
        if cleanup_temp and file_path.exists():
            file_path.unlink()

        return html_path

    except Exception as e:
        print(f"Error converting {file_path}: {e}", file=sys.stderr)
        return None


def generate_stylesheet_hash(stylesheet_path: Path) -> str:
    """Generate a unique stylesheet filename based on its content."""
    if not stylesheet_path or not stylesheet_path.exists():
        return "style.css"

    with open(stylesheet_path, "rb") as f:
        css = f.read()

    checksum = hashlib.sha256(css).hexdigest()[:32]
    return f"style_{checksum}.css"


def process_file(file_path: Path, stylesheet_url: str = None) -> tuple:
    """Process a single file and return (original_path, html_path)."""
    html_path = convert_file_to_html(file_path, stylesheet_url)
    return (file_path, html_path)


def find_all_source_files(root_dir: Path = None) -> list:
    """Find all source files recursively in the directory."""
    if root_dir is None:
        root_dir = Path.cwd()

    source_files = []
    for ext in VALID_EXTENSIONS:
        source_files.extend(root_dir.rglob(f"*{ext}"))

    return source_files


def publish_parallel(root_dir: Path = None, max_workers: int = None):
    """Convert all source files to HTML in parallel."""
    if root_dir is None:
        root_dir = Path.cwd()

    root_dir = Path(root_dir).resolve()

    # Find stylesheet if exists
    stylesheet_path = root_dir / "style.css"
    if stylesheet_path.exists():
        stylesheet_filename = generate_stylesheet_hash(stylesheet_path)
        stylesheet_dest = root_dir / stylesheet_filename

        # Only copy if different
        if not stylesheet_dest.exists():
            shutil.copy(stylesheet_path, stylesheet_dest)

        stylesheet_url = stylesheet_filename
    else:
        stylesheet_url = None

    # Find all source files
    source_files = find_all_source_files(root_dir)

    if not source_files:
        print(f"No source files found in {root_dir}")
        return

    print(f"Found {len(source_files)} files to convert")

    # Process files in parallel
    converted = 0
    errors = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(process_file, file_path, stylesheet_url): file_path for file_path in source_files
        }

        # Process results as they complete
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                original, html_path = future.result()
                if html_path:
                    converted += 1
                    print(f"Converted: {original.relative_to(root_dir)} -> {html_path.relative_to(root_dir)}")
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                print(f"Error processing {file_path.relative_to(root_dir)}: {e}", file=sys.stderr)

    print(f"\nConversion complete: {converted} converted, {errors} errors")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Convert all .rst, .txt, and .md files to HTML recursively")
    parser.add_argument(
        "directory", nargs="?", default=".", help="Root directory to process (default: current directory)"
    )
    parser.add_argument(
        "--workers", type=int, default=os.cpu_count(), help="Number of parallel workers (default: CPU count)"
    )
    parser.add_argument("--force", action="store_true", help="Force re-conversion even if HTML is newer")

    args = parser.parse_args()

    root_dir = Path(args.directory).resolve()
    if not root_dir.exists():
        print(f"Error: Directory '{root_dir}' does not exist", file=sys.stderr)
        sys.exit(1)

    publish_parallel(root_dir, args.workers)


if __name__ == "__main__":
    main()
