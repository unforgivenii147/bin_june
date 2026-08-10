#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import ast
import sys
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def sort_python_script(file_path: Path) -> None:
    try:
        source_code = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return

    lines = source_code.split("\n")
    shebang = ""
    module_docstring = ""
    code_start = 0

    # Extract shebang
    if lines and lines[0].startswith("#!"):
        shebang = lines[0]
        code_start = 1

    # Parse remaining code
    remaining_code = "\n".join(lines[code_start:])

    try:
        tree = ast.parse(remaining_code)
    except SyntaxError as e:
        print(f"Error parsing Python code in {file_path}: {e}")
        return

    # Extract module docstring
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        if isinstance(tree.body[0].value.value, str):
            docstring_node = tree.body[0]
            module_docstring = ast.get_source_segment(remaining_code, docstring_node) or ""
            tree.body.pop(0)

    # Separate __main__ block
    main_block = None
    other_nodes = []

    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            # Check if it's: if __name__ == "__main__"
            if (
                isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
                and len(node.test.ops) == 1
                and isinstance(node.test.ops[0], ast.Eq)
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value == "__main__"
            ):
                main_block = node
                continue
        other_nodes.append(node)

    # Categorize remaining nodes
    imports = []
    constants = []
    classes = []
    functions = []
    misc = []

    for node in other_nodes:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
        elif isinstance(node, ast.Assign):
            is_constant = all(isinstance(target, ast.Name) and target.id.isupper() for target in node.targets)
            if is_constant:
                constants.append(node)
            else:
                misc.append(node)
        elif isinstance(node, ast.ClassDef):
            classes.append(node)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node)
        else:
            misc.append(node)

    # Sort
    constants.sort(key=lambda n: n.targets[0].id if n.targets else "")
    classes.sort(key=lambda n: n.name)
    functions.sort(key=lambda n: n.name)

    # Rebuild sorted code using source segments
    sorted_lines = []

    if shebang:
        sorted_lines.append(shebang)

    if module_docstring:
        sorted_lines.append(module_docstring)

    for section in [imports, misc, constants, classes, functions]:
        for node in section:
            segment = ast.get_source_segment(remaining_code, node)
            if segment:
                sorted_lines.append(segment)
            else:
                print(f"Warning: Could not preserve source for {node}")

    if main_block:
        segment = ast.get_source_segment(remaining_code, main_block)
        if segment:
            sorted_lines.append(segment)

    sorted_code = "\n".join(sorted_lines)

    try:
        with file_path.open("w", encoding="utf-8") as f:
            f.write(sorted_code)
        print(f"Successfully sorted and saved: {file_path}")
    except Exception as e:
        print(f"Error writing to {file_path}: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python sort_script.py <path_to_python_script>")
        sys.exit(1)
    script_path = Path(sys.argv[1])
    sort_python_script(script_path)
