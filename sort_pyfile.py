#!/data/data/com.termux/files/usr/bin/python

import ast
import sys
from pathlib import Path


def sort_python_script(file_path: Path):
    try:
        source_code = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)
    except SyntaxError as e:
        print(f"Error parsing Python code in {file_path}: {e}")
        return
    constants = []
    classes = []
    functions = []
    other_nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            is_constant = True
            for target in node.targets:
                if not isinstance(target, ast.Name) or not target.id.isupper():
                    is_constant = False
                    break
            if is_constant:
                constants.append(node)
            else:
                other_nodes.append(node)
        elif isinstance(node, ast.ClassDef):
            classes.append(node)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node)
        else:
            other_nodes.append(node)
    constants.sort(key=lambda node: node.targets[0].id if node.targets else "")
    classes.sort(key=lambda node: node.name)
    functions.sort(key=lambda node: node.name)
    imports = []
    misc_nodes = []
    for node in other_nodes:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
        else:
            misc_nodes.append(node)
    new_body = imports + misc_nodes + constants + classes + functions
    new_tree = ast.Module(body=new_body, type_ignores=[])
    try:
        import astunparse

        sorted_code = astunparse.unparse(new_tree)
    except ImportError:
        print("Warning: 'astunparse' library not found. Trying built-in 'ast.unparse' (Python 3.9+).")
        try:
            sorted_code = ast.unparse(new_tree)
        except AttributeError:
            print("Error: Your Python version is too old to have 'ast.unparse'.")
            print("Please install the 'astunparse' library: pip install astunparse")
            return
    except Exception as e:
        print(f"Error converting AST back to code: {e}")
        return
    try:
        with file_path.open("w", encoding="utf-8") as f:
            f.write(sorted_code)
        print(f"Successfully sorted and saved: {file_path}")
    except Exception as e:
        print(f"Error writing sorted code back to {file_path}: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python sort_script.py <path_to_python_script>")
        sys.exit(1)
    script_path = Path(sys.argv[1])
    sort_python_script(script_path)
