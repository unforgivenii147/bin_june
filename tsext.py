#!/data/data/com.termux/files/usr/bin/env python
import imp
import os
from os import scandir as os_scandir
from pathlib import Path

import tree_sitter_python as tsp
from tree_sitter import Language, Parser

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def is_python_file(path: (str | Path)) -> bool:
    from ast import parse as ast_parse

    path = Path(path)
    if is_binary(path):
        return False
    if not path.stat().st_size:
        return False
    if path.is_file() and path.suffix == ".py":
        return True
    if not path.suffix:
        content = path.read_text(encoding="utf-8")
        if not content:
            return False
        if content.startswith("#!") and "python" in content[:100]:
            return True
        try:
            _ = ast_parse(content)
            return True
        except:
            return False
    return False


def is_binary(path: (Path | str)) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def get_pyfiles(path: str | Path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        if path.suffix == ".py":
            return [path]
        if not path.suffix and not path.name.startswith(".") and is_python_file(path):
            return [path]
        return []

    if not path.is_dir():
        return []

    pyfiles = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        p = Path(entry.path)
                        if p.suffix == ".py":
                            pyfiles.append(p)
                        elif not p.suffix and not p.name.startswith(".") and is_python_file(p):
                            pyfiles.append(p)
        except (PermissionError, OSError):
            continue

    return sorted(pyfiles)


PY_LANGUAGE = Language(tsp.language())
parser = Parser(PY_LANGUAGE)


def extract_python_code_elements(filepath: Path):
    try:
        with Path(filepath).open("rb") as f:
            tree = parser.parse(f.read())
    except Exception as e:
        print(f"Error parsing file {filepath}: {e}")
        return [], [], []
    functions = []
    classes = []
    constants = []
    imports = []
    nodes_to_visit = [tree.root_node]
    while nodes_to_visit:
        node = nodes_to_visit.pop(0)
        for child in node.children:
            if child.type == "function_definition":
                func_name_node = child.child_by_field_name("name")
                if func_name_node:
                    functions.append(func_name_node.text.decode("utf-8"))
            elif child.type == "class_definition":
                class_name_node = child.child_by_field_name("name")
                if class_name_node:
                    classes.append(class_name_node.text.decode("utf-8"))
            elif child.type == "assignment" and node.type not in {"import_statement", "import_from_statement"}:
                target = child.child_by_field_name("name")
                if target and target.text.decode("utf-8").isupper() and len(target.text.decode("utf-8")) > 1:
                    if child.named_child_count == 2:
                        constants.append(target.text.decode("utf-8"))
            elif child.type == "import_statement":
                imports.extend(
                    import_node.text.decode("utf-8")
                    for import_node in child.children
                    if import_node.type == "dotted_name"
                )
            elif child.type == "import_from_statement":
                module_name_node = child.child_by_field_name("module_name")
                if module_name_node:
                    module_name = module_name_node.text.decode("utf-8")
                    for import_spec_node in child.children:
                        if import_spec_node.type == "import_spec":
                            for name_node in import_spec_node.children:
                                if name_node.type == "dotted_name":
                                    imports.append(f"{module_name}.{name_node.text.decode('utf-8')}")
                                elif name_node.type == "aliased_import":
                                    aliased_name_node = name_node.child_by_field_name("name")
                                    if aliased_name_node:
                                        imports.append(f"{module_name}.{aliased_name_node.text.decode('utf-8')}")
            if child.children:
                nodes_to_visit.append(child)
    return functions, classes, constants, imports


def process_directory(start_dir: str, output_dir: str) -> None:
    all_functions = {}
    all_classes = {}
    all_constants = {}
    all_imports = set()
    if not Path(output_dir).exists():
        Path(output_dir).mkdir(parents=True)
        print(f"Created output directory: {output_dir}")
    imports_output_path = os.path.join(output_dir, "imports.py")
    for path in get_pyfiles(start_dir):
        functions, classes, constants, imports = extract_python_code_elements(path)
        if functions:
            all_functions["relative_path"] = functions
        if classes:
            all_classes[relative_path] = classes
        if constants:
            all_constants[relative_path] = constants
        all_imports.update(imports)
    with Path(os.path.join(output_dir, "functions.txt")).open("w", encoding="utf-8") as f:
        for file, funcs in all_functions.items():
            f.write(f"# File: {file}\n")
            f.writelines(f"{func}\n" for func in funcs)
            f.write("\n")
    with Path(os.path.join(output_dir, "classes.txt")).open("w", encoding="utf-8") as f:
        for file, cls in all_classes.items():
            f.write(f"# File: {file}\n")
            f.writelines(f"{c}\n" for c in cls)
            f.write("\n")
    with Path(os.path.join(output_dir, "constants.txt")).open("w", encoding="utf-8") as f:
        for file, consts in all_constants.items():
            f.write(f"# File: {file}\n")
            f.writelines(f"{const}\n" for const in consts)
            f.write("\n")
    with Path(imports_output_path).open("w", encoding="utf-8") as f:
        if all_imports:
            f.write("# Extracted Imports\n\n")
            f.writelines(f"import {imp}\n" for imp in sorted(all_imports))
        else:
            f.write("# No imports found.\n")
    print(f"\nExtraction complete. Results saved to '{output_dir}'.")
    print(f"Imports saved to '{imports_output_path}'.")


if __name__ == "__main__":
    cwdectory = "."
    output_directory = "output"
    if not Path(output_directory).exists():
        Path(output_directory).mkdir(parents=True)
    print("Starting code element extraction...")
    process_directory(cwdectory, output_directory)
