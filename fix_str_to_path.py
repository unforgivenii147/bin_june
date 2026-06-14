#!/data/data/com.termux/files/usr/bin/python
import os
import re


def add_path_statement(file_path):
    """Add path=Path(path) as first line inside process_file function"""

    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    modified_lines = []
    in_function = False
    function_indent = None
    added = False

    for i, line in enumerate(lines):
        # Check if this line starts a function definition
        if re.match(r"^\s*def process_file\(", line):
            in_function = True
            modified_lines.append(line)
            continue

        # If we're in the function and haven't added the path line yet
        if in_function and not added:
            # Skip empty lines and docstrings
            stripped = line.strip()

            # Skip docstring lines
            if stripped and (stripped.startswith('"""') or stripped.startswith("'''")):
                modified_lines.append(line)
                # If it's a multi-line docstring, we need to track it
                if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                    # This is the start of a docstring, skip until it closes
                    docstring_started = True
                    modified_lines.append(line)
                    continue
                else:
                    # Single line docstring, next line will be the first real code
                    continue

            # Calculate the expected indentation (one level deeper than function def)
            if function_indent is None:
                # Find function line to determine its indentation
                for j in range(i - 1, -1, -1):
                    if re.match(r"^\s*def process_file\(", modified_lines[j]):
                        func_line = modified_lines[j]
                        function_indent = re.match(r"^(\s*)", func_line).group(1) + "    "
                        break

            # Check if this line is indented (actual code inside function)
            current_indent = re.match(r"^(\s*)", line).group(1)

            # If this line has the expected function indentation (or more), add our line before it
            if current_indent.startswith(function_indent.rstrip()) and stripped:
                # Add the path statement before this line
                modified_lines.append(f"{function_indent}path = Path(path)\n")
                print(f"Added 'path = Path(path)' to {file_path}")
                added = True
                in_function = False

        modified_lines.append(line)

    # Write the modified content back
    if added:
        with open(file_path, "w", encoding="utf-8") as file:
            file.writelines(modified_lines)
        return True
    else:
        print(f"Skipping {file_path}: No process_file function found or already has the line")
        return False


def add_path_statement_simple(file_path):
    """Simpler version using regex"""

    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # Check if already exists
    if "path=Path(path)" in content or "path = Path(path)" in content:
        print(f"Skipping {file_path}: path=Path(path) already exists")
        return False

    # Pattern to match function definition and add path line right after, before anything else
    # This handles docstrings, empty lines, etc.
    pattern = r'(def process_file\([^:]*:)\s*\n\s*(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')\s*\n?\s*'

    def replacement(match):
        full_match = match.group(0)
        # Get the indentation from the function line
        func_line = match.group(1)
        indent = re.match(r"^(\s*)", func_line).group(1) + "    "

        # Insert path line after function declaration
        return f"{func_line}\n{indent}path = Path(path)\n" + full_match[len(func_line) :]

    # Try with docstring handling
    new_content = re.sub(pattern, replacement, content, count=1)

    # If no docstring, try simpler pattern
    if new_content == content:
        pattern = r"(def process_file\([^:]*:)\s*\n\s*"

        def replacement2(match):
            indent = re.match(r"^(\s*)", match.group(1)).group(1) + "    "
            return f"{match.group(1)}\n{indent}path = Path(path)\n"

        new_content = re.sub(pattern, replacement2, content, count=1)

    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(new_content)
        print(f"Added 'path = Path(path)' to {file_path}")
        return True

    return False


def process_directory():
    """Process all Python files in current directory"""

    cwd = os.getcwd()
    python_files = [f for f in os.listdir(cwd) if f.endswith(".py") and os.path.isfile(f)]

    if not python_files:
        print("No Python files found in current directory")
        return

    print(f"Found {len(python_files)} Python file(s) to process")
    print("-" * 50)

    modified_count = 0
    for file_name in python_files:
        file_path = os.path.join(cwd, file_name)
        # Try the simple regex version first (more reliable)
        if add_path_statement_simple(file_path):
            modified_count += 1
        else:
            # Fall back to the line-by-line version
            if add_path_statement(file_path):
                modified_count += 1

    print("-" * 50)
    print(f"Modified {modified_count} file(s)")


if __name__ == "__main__":
    process_directory()
