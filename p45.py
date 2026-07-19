#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path

from dh import DOC_TH1, DOC_TH2

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def format_python_file(filepath: Path) -> None:
    if not filepath.exists():
        print(f"Error: File not found at {filepath}", file=sys.stderr)
        return
    content = ""
    backup_filepath = filepath.with_name(filepath.name + ".bak")
    try:
        with (
            filepath.open("r", encoding="utf-8") as f_in,
            backup_filepath.open("w", encoding="utf-8") as f_bak,
        ):
            content = f_in.read()
            f_bak.write(content)
    except OSError as e:
        print(f"Error creating backup file {backup_filepath.name}: {e}", file=sys.stderr)
        return
    formatted_lines = []
    lines = content.splitlines()
    in_multiline_string = False
    current_multiline_string_lines = []
    string_type = ""
    for _i, line in enumerate(lines):
        stripped_line = line.strip()
        if "# type:" in stripped_line:
            continue
        if stripped_line.startswith("#!"):
            continue
        if stripped_line.startswith((DOC_TH1, DOC_TH2)):
            if not in_multiline_string:
                in_multiline_string = True
                string_type = stripped_line[:3]
                current_multiline_string_lines = [line]
            else:
                current_multiline_string_lines.append(line)
                if line.strip().endswith(string_type) and len(line.strip()) > len(string_type):
                    in_multiline_string = False
                    processed_string = "\n".join(current_multiline_string_lines)
                    content_to_wrap = processed_string[len(string_type) : -len(string_type)]
                    wrapped_content = textwrap.fill(
                        content_to_wrap,
                        width=35,
                        initial_indent=string_type,
                        subsequent_indent=string_type + " " * (len(string_type) - 1),
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                    if not wrapped_content.endswith(string_type):
                        wrapped_content += string_type
                    formatted_lines.append(wrapped_content)
                    current_multiline_string_lines = []
                    string_type = ""
            continue
        if in_multiline_string:
            current_multiline_string_lines.append(line)
            if line.strip().endswith(string_type) and len(line.strip()) > len(string_type):
                in_multiline_string = False
                processed_string = "\n".join(current_multiline_string_lines)
                content_to_wrap = processed_string[len(string_type) : -len(string_type)]
                wrapped_content = textwrap.fill(
                    content_to_wrap,
                    width=35,
                    initial_indent=string_type,
                    subsequent_indent=string_type + " " * (len(string_type) - 1),
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                if not wrapped_content.endswith(string_type):
                    wrapped_content += string_type
                formatted_lines.append(wrapped_content)
                current_multiline_string_lines = []
                string_type = ""
            continue
        comment_index = line.find("#")
        if comment_index != -1:
            code_part = line[:comment_index]
            comment_part = line[comment_index:].strip()
            if comment_part:
                comment_indent = " " * (len(line) - len(line.lstrip()))
                comment_content = comment_part[1:].strip()
                wrapped_comment = textwrap.fill(
                    comment_content,
                    width=35,
                    initial_indent=comment_indent + "# ",
                    subsequent_indent=comment_indent + "# ",
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                formatted_lines.append(code_part + wrapped_comment[len(comment_indent + "# ") :])
            else:
                formatted_lines.append(line)
        else:
            formatted_lines.append(line)
    if in_multiline_string:
        formatted_lines.extend(current_multiline_string_lines)
    final_formatted_content = "\n".join(formatted_lines)
    try:
        ast.parse(final_formatted_content)
        try:
            Path(filepath).write_text(final_formatted_content, encoding="utf-8")
            print(f"Successfully formatted {filepath}. Backup created at {backup_filepath}")
        except OSError as e:
            print(f"Error writing formatted content to {filepath}: {e}", file=sys.stderr)
    except SyntaxError as e:
        temp_file = Path("temporary.py")
        temp_file.write_text(final_formatted_content, encoding="utf-8")
        print(
            f"Error: Formatted code is not parsable by AST. Aborting write operation for {filepath}.",
            file=sys.stderr,
        )
        print(f"AST Syntax Error: {e}", file=sys.stderr)
        Path(backup_filepath).replace(filepath)
        print(f"Restored {filepath} from backup.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python format_python.py <file_path>")
        sys.exit(1)
    file_to_format = Path(sys.argv[1])
    format_python_file(file_to_format)
