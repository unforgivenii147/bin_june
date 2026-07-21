#!/data/data/com.termux/files/usr/bin/env python
"""
Convert Python package METADATA file to Jupyter notebook.
Strips metadata headers and converts code/markdown sections to notebook cells.
Output filename is based on the package name found in the header.
"""

import json
import re
import sys
from pathlib import Path


def parse_metadata_section(lines):
    """Parse the initial metadata section and extract package name and version."""
    metadata = {}
    current_key = None
    end_line = 0

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Handle multi-line fields (indented continuation)
        if line.startswith(" ") or line.startswith("\t"):
            if current_key and current_key not in [
                "Requires-Dist",
                "Provides-Extra",
                "Dynamic",
                "Classifier",
                "Keywords",
                "Project-URL",
            ]:
                if current_key in metadata:
                    metadata[current_key] += " " + line_stripped
            continue

        # Stop when we hit empty line or non-metadata content (no colon)
        if not line_stripped or ":" not in line_stripped:
            end_line = i
            break

        # Parse key: value pairs
        if ":" in line_stripped:
            key, value = line_stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            # Store only if not in skip list
            if key not in [
                "Author",
                "Author-Email",
                "Maintainer",
                "Maintainer-Email",
                "Home-Page",
                "Download-URL",
                "Project-URL",
                "Requires-Dist",
                "Provides-Extra",
                "Dynamic",
                "Classifier",
                "Keywords",
                "License",
                "License-Expression",
            ]:
                metadata[key] = value
                current_key = key
            else:
                current_key = None
        else:
            current_key = None

        end_line = i + 1

    return metadata, end_line


def find_section_boundaries(content, start_pos=0):
    """Find code blocks and markdown sections."""
    sections = []
    pos = start_pos

    # Pattern for code blocks
    code_pattern = re.compile(r"```(python|shell|bash|sh|py)\s*\n(.*?)```", re.DOTALL)

    while pos < len(content):
        # Look for code blocks
        code_match = code_pattern.search(content, pos)

        if code_match:
            # Add markdown section before code block if exists
            if code_match.start() > pos:
                md_text = content[pos : code_match.start()].strip()
                if md_text:
                    sections.append(("markdown", md_text))

            # Add code block
            code_text = code_match.group(2).strip()
            sections.append(("code", code_text))

            pos = code_match.end()
        else:
            # Add remaining as markdown
            remaining = content[pos:].strip()
            if remaining:
                sections.append(("markdown", remaining))
            break

    return sections


def convert_metadata_to_notebook(metadata_file_path):
    """Convert METADATA file to Jupyter notebook."""

    # Read the metadata file
    with open(metadata_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    # Parse metadata section
    metadata, content_start = parse_metadata_section(lines)

    # Get package name and version
    pkg_name = metadata.get("Name", "unknown_package")
    pkg_version = metadata.get("Version", "0.0.0")

    # Clean package name for filename
    safe_pkg_name = re.sub(r"[^\w\-_]", "_", pkg_name)
    output_path = f"{safe_pkg_name}.ipynb"

    # Reconstruct content after metadata
    remaining_content = "\n".join(lines[content_start:])

    # Find sections
    sections = find_section_boundaries(remaining_content)

    # Build notebook structure
    notebook = {
        "cells": [],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.8.0",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    # Add title cell
    title_content = f"# {pkg_name} v{pkg_version}\n\nConverted from METADATA file"
    title_cell = {"cell_type": "markdown", "metadata": {}, "source": [title_content]}
    notebook["cells"].append(title_cell)

    # Add sections as cells
    for cell_type, content in sections:
        if cell_type == "markdown":
            cell = {"cell_type": "markdown", "metadata": {}, "source": [content]}
        else:  # code cell
            cell = {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [content]}
        notebook["cells"].append(cell)

    # Write notebook
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)

    print(f"Package: {pkg_name} v{pkg_version}")
    print(f"Notebook created: {output_path}")
    print(f"Total cells: {len(notebook['cells'])}")

    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python metadata_to_notebook.py <METADATA_file>")
        print("Output will be saved as <package_name>.ipynb")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print(f"Error: File '{input_file}' not found")
        sys.exit(1)

    convert_metadata_to_notebook(input_file)


if __name__ == "__main__":
    main()
