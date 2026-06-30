#!/data/data/com.termux/files/usr/bin/env python
"""
Convert escaped regex strings back to raw string format.
Handles all re module functions (compile, sub, findall, match, search, etc.).
Processes Python files recursively with parallel processing.
"""

import ast
import re
from pathlib import Path
from multiprocessing import Pool
from typing import Optional, Tuple, List
import sys


# Common re module functions that accept regex patterns
RE_FUNCTIONS = {
    "compile",
    "search",
    "match",
    "fullmatch",
    "split",
    "findall",
    "finditer",
    "sub",
    "subn",
    "escape",
    "purge",
    "Pattern",
}

# Pattern to find re.FUNCTION() calls with string arguments
# Matches: re.func(...) with various argument patterns
RE_CALL_PATTERN = re.compile(r"\bre\.(" + "|".join(RE_FUNCTIONS) + r")\s*\(", re.IGNORECASE)


def needs_raw_string(string_content: str) -> bool:
    """
    Check if a string should be converted to raw format.
    Heuristics: contains backslash escape sequences typical of regex.
    """
    # Count backslash escape sequences
    escape_sequences = re.findall(r'\\[\\abfnrtv"\']', string_content)
    escape_count = len(escape_sequences)

    # Common regex patterns
    regex_indicators = [
        r"\d",
        r"\w",
        r"\s",
        r"\S",
        r"\W",
        r"\D",  # character classes
        r"\[",
        r"\]",  # bracket expressions
        r"\(",
        r"\)",  # groups
        r"\|",
        r"\^",
        r"\$",  # alternation, anchors
        r"\+",
        r"\*",
        r"\?",  # quantifiers
        r"\{",
        r"\}",  # repetition
        r"\.",
        r"\b",
        r"\B",  # special chars
    ]

    has_regex_pattern = any(pattern in string_content for pattern in regex_indicators)

    # Need raw string if: multiple backslashes OR (has backslash AND regex pattern)
    return escape_count >= 2 or (escape_count >= 1 and has_regex_pattern)


def extract_and_convert_strings(content: str) -> Optional[str]:
    """
    Extract re.function() calls and convert their regex string arguments.
    Returns converted content or None if no changes made.
    """
    original_content = content

    # Parse with AST to find re.function calls
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None  # Can't parse, skip

    # Collect all string nodes and their positions
    string_positions = {}

    class StringVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            # Check if this is a re.FUNCTION call
            if isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "re"
                    and node.func.attr in RE_FUNCTIONS
                ):
                    # Check first argument(s) for string patterns
                    if node.args:
                        arg = node.args[0]
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            # Store position and string info
                            string_positions[arg.end_col_offset] = {
                                "value": arg.value,
                                "lineno": arg.lineno,
                                "col_offset": arg.col_offset,
                                "end_col": arg.end_col_offset,
                            }

            self.generic_visit(node)

    visitor = StringVisitor()
    visitor.visit(tree)

    if not string_positions:
        return None

    # Convert strings that need raw format
    lines = content.split("\n")
    converted = False

    for end_col, info in string_positions.items():
        string_val = info["value"]
        lineno = info["lineno"] - 1  # 0-indexed

        if needs_raw_string(string_val):
            # Find the string in the line and convert it
            line = lines[lineno]
            col_offset = info["col_offset"]
            end_col_offset = info["end_col"]

            # Extract the original string literal
            original_literal = line[col_offset:end_col_offset]

            # Determine quote style
            if original_literal.startswith('"""') or original_literal.startswith("'''"):
                continue  # Skip triple-quoted strings

            quote_char = original_literal[0]

            # Check if already raw
            if original_literal.startswith(('r"', "r'", 'r"""', "r'''")):
                continue

            # Convert to raw string
            try:
                # Unescape to get raw content
                unescaped = string_val
                new_literal = f"r{quote_char}{unescaped}{quote_char}"

                # Replace in line
                new_line = line[:col_offset] + new_literal + line[end_col_offset:]
                lines[lineno] = new_line
                converted = True
            except Exception:
                continue

    if not converted:
        return None

    return "\n".join(lines)


def validate_python_file(content: str) -> bool:
    """Validate that content is valid Python using AST."""
    try:
        ast.parse(content)
        return True
    except SyntaxError as e:
        print(f"  ✗ Syntax error: {e}", file=sys.stderr)
        return False


def process_file(filepath: Path) -> Tuple[Path, bool, str]:
    """
    Process a single Python file.
    Returns (filepath, success, message).
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return filepath, False, f"Failed to read: {e}"

    converted_content = extract_and_convert_strings(content)

    if converted_content is None:
        return filepath, True, "No changes needed"

    # Validate converted content
    if not validate_python_file(converted_content):
        return filepath, False, "Validation failed, skipping"

    try:
        filepath.write_text(converted_content, encoding="utf-8")
        return filepath, True, "✓ Converted and saved"
    except Exception as e:
        return filepath, False, f"Failed to write: {e}"


def main():
    """Main entry point."""
    current_dir = Path.cwd()
    python_files = list(current_dir.rglob("*.py"))

    if not python_files:
        print("No Python files found in current directory")
        return

    print(f"Found {len(python_files)} Python files")
    print(f"Processing with parallel workers...")
    print(f"Target re functions: {', '.join(sorted(RE_FUNCTIONS))}\n")

    # Process files in parallel
    with Pool() as pool:
        results = pool.map(process_file, python_files)

    # Report results
    successful = sum(1 for _, success, _ in results if success)
    changed = sum(1 for _, success, msg in results if success and "✓" in msg)

    print("\n" + "=" * 70)
    for filepath, success, message in results:
        status = "✓" if success else "✗"
        rel_path = filepath.relative_to(current_dir)
        print(f"{status} {rel_path}: {message}")

    print("=" * 70)
    print(f"\nSummary: {successful}/{len(python_files)} processed successfully")
    print(f"         {changed} files converted")


if __name__ == "__main__":
    main()
