#!/data/data/com.termux/files/usr/bin/python
import re
from pathlib import Path

# Mapping of os.path functions to their pathlib equivalents
OS_PATH_TO_PATHLIB = {
    r"os\.path\.join\(": "Path(",
    r"os\.path\.dirname\(": ".parent",
    r"os\.path\.basename\(": ".name",
    r"os\.path\.exists\(": ".exists()",
    r"os\.path\.isfile\(": ".is_file()",
    r"os\.path\.isdir\(": ".is_dir()",
    r"os\.path\.abspath\(": "Path(",
    r"os\.path\.relpath\(": "Path(",
    r"os\.path\.normpath\(": "Path(",
    r"os\.path\.expanduser\(": "Path(",
    r"os\.path\.getsize\(": ".stat().st_size",
    r"os\.path\.getmtime\(": ".stat().st_mtime",
    r"os\.path\.getatime\(": ".stat().st_atime",
    r"os\.path\.split\(": ".parts",
    r"os\.path\.splitext\(": ".suffix",
}

# Patterns for os.path imports
OS_PATH_IMPORT_PATTERNS = [
    r"import os\.path",
    r"from os\.path import",
    r"from os import path",
    r"import os",
]


def refactor_file(file_path):
    """Refactor a single Python file to replace os.path with pathlib."""
    content = file_path.read_text(encoding="utf-8")
    original_content = content

    # Replace os.path imports with pathlib
    for pattern in OS_PATH_IMPORT_PATTERNS:
        content = re.sub(pattern, "from pathlib import Path", content)

    # Replace os.path.* calls with pathlib equivalents
    for os_path_func, pathlib_replacement in OS_PATH_TO_PATHLIB.items():
        content = re.sub(os_path_func, pathlib_replacement, content)

    # Handle os.path.join with multiple arguments
    content = re.sub(
        r"Path\(([^)]+)\)",
        lambda m: f"Path({m.group(1).replace(' ', '').replace(',', ', ')})",
        content,
    )

    # Handle os.path.join with variables
    content = re.sub(r"Path\(([^)]+)\)", lambda m: f"Path({m.group(1)})", content)

    # Handle os.path.dirname and os.path.basename
    content = re.sub(r"(\w+)\s*\.parent", r"Path(\1).parent", content)
    content = re.sub(r"(\w+)\s*\.name", r"Path(\1).name", content)

    # Handle os.path.exists, isfile, isdir
    content = re.sub(r"(\w+)\s*\.exists\(\)", r"Path(\1).exists()", content)
    content = re.sub(r"(\w+)\s*\.is_file\(\)", r"Path(\1).is_file()", content)
    content = re.sub(r"(\w+)\s*\.is_dir\(\)", r"Path(\1).is_dir()", content)

    # Handle os.path.abspath, relpath, normpath, expanduser
    content = re.sub(
        r"Path\(([^)]+)\)",
        lambda m: f"Path({m.group(1)}).resolve()" if "abspath" in m.group(0) else m.group(0),
        content,
    )

    # Handle os.path.getsize, getmtime, getatime
    content = re.sub(r"(\w+)\s*\.stat\(\)\s*\.st_size", r"Path(\1).stat().st_size", content)
    content = re.sub(r"(\w+)\s*\.stat\(\)\s*\.st_mtime", r"Path(\1).stat().st_mtime", content)
    content = re.sub(r"(\w+)\s*\.stat\(\)\s*\.st_atime", r"Path(\1).stat().st_atime", content)

    # Add pathlib import if not already present
    if "from pathlib import Path" not in content and "import pathlib" not in content:
        content = "from pathlib import Path\n" + content

    # Write the refactored content back to the file if changes were made
    if content != original_content:
        file_path.write_text(content, encoding="utf-8")
        return True
    return False


def refactor_directory(directory):
    """Refactor all Python files in the directory recursively."""
    python_files = directory.rglob("*.py")
    refactored_count = 0

    for file_path in python_files:
        if refactor_file(file_path):
            print(f"Refactored: {file_path.relative_to(Path.cwd())}")
            refactored_count += 1

    print(f"\nRefactored {refactored_count} files.")


if __name__ == "__main__":
    current_dir = Path.cwd()
    print(f"Refactoring Python files in: {current_dir}")
    refactor_directory(current_dir)
