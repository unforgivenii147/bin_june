#!/data/data/com.termux/files/usr/bin/python

import ast
import re
import sys
from ast import Module
from collections import defaultdict
from pathlib import Path


def get_imported_names(tree):
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, alias.name, alias.asname))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                name = alias.name
                asname = alias.asname or name
                imports.append((name, module, asname))
    return imports


def get_used_names(tree, module_name):
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == module_name:
                used_names.add(node.attr)
    return used_names


def transform_imports(tree: Module, source_lines: list[str]):
    imports = get_imported_names(tree)
    simple_imports = defaultdict(list)
    for name, module, alias in imports:
        if name == module:
            simple_imports[module].append((name, alias))
    replacements = {}
    for module, names in simple_imports.items():
        used = get_used_names(tree, module)
        if not used:
            continue
        for name, alias in names:
            if name in used:
                replacements[name] = new_name
    if not replacements:
        return source_lines, False
    new_lines = []
    in_imports = True
    for line in source_lines:
        stripped = line.strip()
        if in_imports and (stripped.startswith("import ") or stripped.startswith("from ")):
            continue
        elif in_imports and (stripped == "" or stripped.startswith("#")):
            new_lines.append(line)
            continue
        else:
            in_imports = False
            new_lines.append(line)
    insert_pos = 0
    for i, line in enumerate(new_lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            insert_pos = i
            break
    new_import_lines = []
    for module, names in simple_imports.items():
        used = get_used_names(tree, module)
        for name, alias in names:
            if name in used:
                new_import_lines.append(f"from {module} import {name} as {new_name}\n")
    new_lines[insert_pos:insert_pos] = new_import_lines

    def replace_name(match):
        name = match.group(0)
        if name in replacements:
            return replacements[name]
        return name

    for i in range(len(new_lines)):
        stripped = new_lines[i].strip()
        if stripped.startswith("import ") or stripped.startswith("from ") and "import" in stripped:
            continue
        line = new_lines[i]
        new_lines[i] = re.sub(
            "\\b(" + "|".join(map(re.escape, replacements.keys())) + ")\\b", lambda m: replacements[m.group(1)], line
        )
    return new_lines, True


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python script.py <python_file>", file=sys.stderr)
        sys.exit(1)
    filepath = sys.argv[1]
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        sys.exit(1)
    if not path.suffix == ".py":
        print(f"Error: '{filepath}' is not a Python file.", file=sys.stderr)
        sys.exit(1)
    try:
        content = path.read_text()
        source_lines = content.splitlines(keepends=True)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Error: Original file has syntax errors: {e}", file=sys.stderr)
        sys.exit(1)
    new_lines, transformed = transform_imports(tree, source_lines)
    if not transformed:
        print(f"No transformations needed for '{filepath}'.")
        return
    new_content = "".join(new_lines)
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print(f"Error: Transformed file has syntax errors: {e}", file=sys.stderr)
        print("Original file unchanged.", file=sys.stderr)
        sys.exit(1)
    try:
        path.write_text(new_content)
        print(f"Successfully updated '{filepath}'.")
    except Exception as e:
        print(f"Error writing file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
