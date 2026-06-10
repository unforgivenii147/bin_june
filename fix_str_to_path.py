#!/data/data/com.termux/files/usr/bin/python
import os
import re


def add_path_statement(file_path):
    """Add path=Path(path) to process_file function if not already present"""

    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # Check if the file contains process_file function
    if "def process_file(" not in content:
        print(f"Skipping {file_path}: No process_file function found")
        return False

    # Check if path=Path(path) already exists
    if "path=Path(path)" in content:
        print(f"Skipping {file_path}: path=Path(path) already exists")
        return False

    # Pattern to find the line after the function definition
    # This looks for indentation after the function definition line
    lines = content.split("\n")
    modified_lines = []
    found_function = False
    lines_added = 0

    for i, line in enumerate(lines):
        modified_lines.append(line)

        if found_function and lines_added == 0:
            # Check if this line is the first non-empty line after function definition
            stripped = line.strip()
            if stripped and not stripped.startswith("@"):  # Skip decorators
                # Calculate indentation of the next line
                indent = re.match(r"^(\s*)", line).group(1)
                # Add the path statement with proper indentation
                modified_lines.append(f"{indent}path = Path(path)")
                print(f"Added 'path = Path(path)' to {file_path}")
                lines_added += 1
                found_function = False

        # Detect when we find the function definition (but don't add the line yet)
        if re.match(r"^\s*def process_file\(", line):
            found_function = True

    # Write the modified content back if changes were made
    if lines_added > 0:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write("\n".join(modified_lines))
        return True

    # Alternative approach using regex for more complex cases
    if not lines_added:
        return add_path_with_regex(file_path, content)

    return False


def add_path_with_regex(file_path, content):
    """Alternative method using regex to add the path statement"""

    # Pattern to find the line right after the function definition
    # Looking for the opening brace and the next non-empty line
    pattern = r"(def process_file\([^:]*:)\s*\n(\s*)"

    def replacement(match):
        indent = match.group(2)
        return f"{match.group(1)}\n{indent}path = Path(path)\n{indent}"

    new_content = re.sub(pattern, replacement, content, count=1)

    if new_content != content:
        # Check again if path=Path(path) was added successfully
        if "path=Path(path)" in new_content:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(new_content)
            print(f"Added 'path = Path(path)' to {file_path} (using regex method)")
            return True

    return False


def process_directory():
    """Process all Python files in current directory"""

    current_dir = os.getcwd()
    python_files = [f for f in os.listdir(current_dir) if f.endswith(".py") and os.path.isfile(f)]

    if not python_files:
        print("No Python files found in current directory")
        return

    print(f"Found {len(python_files)} Python file(s) to process")
    print("-" * 50)

    modified_count = 0
    for file_name in python_files:
        file_path = os.path.join(current_dir, file_name)
        if add_path_statement(file_path):
            modified_count += 1

    print("-" * 50)
    print(f"Modified {modified_count} file(s)")


if __name__ == "__main__":
    process_directory()
