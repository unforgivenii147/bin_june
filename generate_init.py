#!/data/data/com.termux/files/home/.local/bin/python
"""
Generate __init__.py files that import all public functions and classes
from Python modules in the current directory.
"""

import ast
import sys
from pathlib import Path


def get_public_names(file_path: Path) -> list[str]:
    """
    Parse a Python file and extract all public functions and classes.

    Args:
        file_path: Path to the Python file

    Returns:
        List of public function and class names
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return []

    public_names = []

    for node in ast.walk(tree):
        # Check for function definitions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                public_names.append(node.name)

        # Check for class definitions
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                public_names.append(node.name)

    return sorted(set(public_names))  # Remove duplicates and sort


def get_python_modules(directory: Path) -> list[Path]:
    """
    Get all Python modules (excluding __init__.py) in the directory.

    Args:
        directory: Directory to search

    Returns:
        List of paths to Python modules
    """
    modules = []

    for file_path in directory.glob("*.py"):
        # Skip __init__.py and files starting with underscore (private modules)
        if file_path.name != "__init__.py" and not file_path.name.startswith("_"):
            modules.append(file_path)

    return sorted(modules)


def generate_init_content(modules: list[Path]) -> str:
    """
    Generate the content for __init__.py.

    Args:
        modules: List of Python module paths

    Returns:
        String content for __init__.py
    """
    lines = []
    all_exports = []

    for module in modules:
        module_name = module.stem  # Get filename without .py extension
        public_names = get_public_names(module)

        if public_names:
            # Create the import line
            names_str = ", ".join(public_names)
            lines.append(f"from .{module_name} import {names_str}")

            # Add to __all__
            all_exports.extend(public_names)

    # Add __all__ if there are any exports
    if all_exports:
        lines.append("")
        all_str = ", ".join(repr(name) for name in all_exports)
        lines.append(f"__all__ = [{all_str}]")

    # Add trailing newline
    if lines:
        lines.append("")

    return "\n".join(lines)


def main():
    """Main function to generate __init__.py."""
    current_dir = Path.cwd()

    print(f"Scanning directory: {current_dir}")

    # Get all Python modules in the current directory
    modules = get_python_modules(current_dir)

    if not modules:
        print("No Python modules found in the current directory.")
        return

    print(f"Found {len(modules)} Python module(s):")
    for module in modules:
        public_names = get_public_names(module)
        print(f"  - {module.name}: {len(public_names)} public name(s)")

    # Generate the __init__.py content
    init_content = generate_init_content(modules)

    # Write to __init__.py
    init_file = current_dir / "__init__.py"

    if init_file.exists():
        response = input(f"\n{init_file} already exists. Overwrite? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            return

    with open(init_file, "w", encoding="utf-8") as f:
        f.write(init_content)

    print(f"\nCreated {init_file}")
    print("\nGenerated content:")
    print("-" * 40)
    print(init_content)
    print("-" * 40)


if __name__ == "__main__":
    main()
