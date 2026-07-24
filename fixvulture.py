#!/data/data/com.termux/files/home/.local/bin/python
"""
Fix unused code based on Vulture output.
Reads Vulture findings from stdin or a file and fixes the issues in-place.
"""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from typing import dict, list, set, tuple

VULTURE_LINE_PATTERN = re.compile(
    r"^(.+?):(\d+):\s+(unused\s+(function|variable|class|attribute|method|import)\s+'([^']+)'|unreachable code after '(\w+)'|redundant if-condition|unreachable 'else' block|unused import '([^']+)'\s+\(\d+% confidence\))$"
)


def parse_vulture_output(lines: list[str]) -> dict[str, list[tuple[int, str, str]]]:
    results = defaultdict(list)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = VULTURE_LINE_PATTERN.match(line)
        if not match:
            continue

        filepath = match.group(1)
        line_num = int(match.group(2))
        full_message = match.group(3)

        # Extract type and name
        issue_type = None
        name = None

        if match.group(4):  # unused function/variable/class/attribute/method
            issue_type = "unused_" + match.group(4)
            name = match.group(5)
        elif match.group(6):  # unreachable code after
            issue_type = "unreachable_after"
            name = match.group(6)
        elif "redundant if-condition" in full_message:
            issue_type = "redundant_if"
            name = ""
        elif "unreachable 'else' block" in full_message:
            issue_type = "unreachable_else"
            name = ""
        elif match.group(7):  # unused import
            issue_type = "unused_import"
            name = match.group(7)
        else:
            issue_type = "other"
            name = ""

        results[filepath].append((line_num, issue_type, name))

    return dict(results)


def fix_file(filepath: str, issues: list[tuple[int, str, str]]) -> bool:
    """Fix issues in a single file."""
    if not os.path.exists(filepath):
        print(f"Warning: File not found: {filepath}")
        return False

    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False

    original_lines = lines.copy()
    modified = False

    # Sort issues by line number (descending to preserve line numbers)
    issues_sorted = sorted(issues, key=lambda x: x[0], reverse=True)

    # Track lines to remove (for multi-line removals)
    lines_to_remove: set[int] = set()

    for line_num, issue_type, name in issues_sorted:
        idx = line_num - 1  # Convert to 0-based index

        if idx < 0 or idx >= len(lines):
            continue

        if idx in lines_to_remove:
            continue

        line = lines[idx]

        try:
            if issue_type == "unused_variable":
                # Comment out the line with variable assignment
                lines[idx] = _comment_out_variable(line, name)
                modified = True

            elif issue_type == "unused_function":
                # Remove the entire function definition
                func_lines = _get_function_lines(lines, idx)
                for i in range(func_lines[0], func_lines[1] + 1):
                    lines_to_remove.add(i)
                modified = True

            elif issue_type == "unused_method":
                # Remove the entire method
                func_lines = _get_function_lines(lines, idx)
                for i in range(func_lines[0], func_lines[1] + 1):
                    lines_to_remove.add(i)
                modified = True

            elif issue_type == "unused_class":
                # Remove the entire class
                class_lines = _get_class_lines(lines, idx)
                for i in range(class_lines[0], class_lines[1] + 1):
                    lines_to_remove.add(i)
                modified = True

            elif issue_type == "unused_attribute":
                # Comment out the attribute line
                lines[idx] = _comment_out_line(line)
                modified = True

            elif issue_type == "unused_import":
                # Remove the import
                lines[idx] = _comment_out_line(line)
                modified = True

            elif issue_type in ("unreachable_after", "unreachable_else"):
                # Comment out unreachable code
                _get_indent(line)
                end_idx = _find_block_end(lines, idx)
                for i in range(idx, end_idx + 1):
                    if i not in lines_to_remove:
                        lines_to_remove.add(i)
                modified = True

            elif issue_type == "redundant_if":
                # Comment out the redundant if condition
                lines[idx] = _comment_out_line(line)
                modified = True

        except Exception as e:
            print(f"Error processing {filepath}:{line_num} - {e}")
            continue

    # Remove marked lines (in reverse order)
    if lines_to_remove:
        lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
        # Clean up extra blank lines (max 2 consecutive)
        lines = _cleanup_blank_lines(lines)
        modified = True

    # Write back if modified
    if modified:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"Fixed: {filepath}")
            return True
        except Exception as e:
            print(f"Error writing {filepath}: {e}")
            # Restore original
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(original_lines)
            return False

    return False


def _comment_out_variable(line: str, name: str) -> str:
    """Comment out a variable assignment."""
    indent = _get_indent(line)
    return f"{indent}# REMOVED: {line.strip()}\n"


def _comment_out_line(line: str) -> str:
    """Comment out a line."""
    indent = _get_indent(line)
    return f"{indent}# REMOVED: {line.strip()}\n"


def _get_indent(line: str) -> str:
    """Get the indentation of a line."""
    return line[: len(line) - len(line.lstrip())]


def _get_function_lines(lines: list[str], start_idx: int) -> tuple[int, int]:
    """Get the start and end line indices of a function/method definition."""
    # Check for decorators above
    func_start = start_idx
    while func_start > 0:
        prev_line = lines[func_start - 1].strip()
        if prev_line.startswith("@"):
            func_start -= 1
        else:
            break

    # Find the function body
    start_line = lines[start_idx]
    indent = len(start_line) - len(start_line.lstrip())

    end_idx = start_idx + 1
    while end_idx < len(lines):
        line = lines[end_idx]
        if line.strip() and not line.strip().startswith("#"):
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent:
                break
        end_idx += 1

    return func_start, end_idx - 1


def _get_class_lines(lines: list[str], start_idx: int) -> tuple[int, int]:
    """Get the start and end line indices of a class definition."""
    # Similar to function but for classes
    class_start = start_idx
    while class_start > 0:
        prev_line = lines[class_start - 1].strip()
        if prev_line.startswith("@"):
            class_start -= 1
        else:
            break

    start_line = lines[start_idx]
    indent = len(start_line) - len(start_line.lstrip())

    end_idx = start_idx + 1
    while end_idx < len(lines):
        line = lines[end_idx]
        if line.strip() and not line.strip().startswith("#"):
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent:
                break
        end_idx += 1

    return class_start, end_idx - 1


def _find_block_end(lines: list[str], start_idx: int) -> int:
    """Find the end of a code block."""
    indent = _get_indent(lines[start_idx])
    end_idx = start_idx
    while end_idx + 1 < len(lines):
        next_line = lines[end_idx + 1]
        if next_line.strip() and not next_line.strip().startswith("#"):
            next_indent = _get_indent(next_line)
            if len(next_indent) <= len(indent) and next_line.strip():
                break
        end_idx += 1
    return end_idx


def _cleanup_blank_lines(lines: list[str]) -> list[str]:
    """Remove excessive blank lines (keep max 2 consecutive)."""
    cleaned = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)
    return cleaned


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Read from file
        vulture_file = sys.argv[1]
        try:
            with open(vulture_file) as f:
                vulture_output = f.readlines()
        except FileNotFoundError:
            print(f"Error: File not found: {vulture_file}")
            sys.exit(1)
    else:
        # Read from stdin
        print("Reading Vulture output from stdin...")
        vulture_output = sys.stdin.readlines()

    if not vulture_output:
        print("No input provided.")
        sys.exit(0)

    # Parse the output
    issues_by_file = parse_vulture_output(vulture_output)

    if not issues_by_file:
        print("No issues found to fix.")
        sys.exit(0)

    print(f"Found issues in {len(issues_by_file)} files.")

    # Confirm with user
    print("\nThe following files will be modified:")
    for filepath in issues_by_file:
        print(f"  {filepath}: {len(issues_by_file[filepath])} issues")

    response = input("\nProceed with fixes? (y/N): ").strip().lower()
    if response not in ("y", "yes"):
        print("Aborted.")
        sys.exit(0)

    # Fix files
    fixed_count = 0
    for filepath, issues in issues_by_file.items():
        if fix_file(filepath, issues):
            fixed_count += 1

    print(f"\nDone! Fixed {fixed_count} files.")


if __name__ == "__main__":
    main()
