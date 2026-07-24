#!/data/data/com.termux/files/home/.local/bin/python
import json
import collections
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import ast
import astor  # Highly recommended: run 'pip install astor' for reliable source code generation from AST

# 1. Load the definitions from your json file
REPEATED_JSON_PATH = Path("repeated.json")


def load_refactoring_maps():
    """Maps filename strings to the specific object names that need removal."""
    with open(REPEATED_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    file_to_objects = collections.defaultdict(list)
    for item in data:
        obj_name = item["name"]
        for file_path_str in item["files"]:
            p = Path(file_path_str)
            # Match files by name in current working directory
            file_to_objects[p.name].append(obj_name)

    return file_to_objects


class ASTStripper(ast.NodeTransformer):
    """AST Transformer that removes specific Functions, Classes, and Constants by name."""

    def __init__(self, target_names):
        super().__init__()
        self.target_names = set(target_names)
        self.removed_something = False

    def visit_FunctionDef(self, node):
        if node.name in self.target_names:
            self.removed_something = True
            return None  # Removes node
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        if node.name in self.target_names:
            self.removed_something = True
            return None  # Removes node
        return self.generic_visit(node)

    def visit_Assign(self, node):
        # Targets top-level assignments (Constants like SKIP_DIRS)
        # Handles single targets: SKIP_DIRS = ...
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in self.target_names:
                self.removed_something = True
                return None
        return self.generic_visit(node)


def refactor_single_file(file_path: Path, objects_to_remove: list):
    """Parses, strips objects, inserts the 'dh' package imports, and writes back."""
    try:
        source_code = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)
    except Exception as e:
        print(f"❌ Error parsing {file_path.name}: {e}")
        return

    # Strip the nodes via AST matching
    stripper = ASTStripper(objects_to_remove)
    modified_tree = stripper.visit(tree)
    ast.fix_missing_locations(modified_tree)

    if not stripper.removed_something:
        print(f"➖ No matching structural nodes found inside {file_path.name}")
        return

    # Build the required import line dynamically based on what objects were present
    import_names = ", ".join(sorted(objects_to_remove))
    import_statement = f"from dh import {import_names}\n"

    try:
        # Convert AST back to valid Python code string safely using astor
        cleaned_source = astor.to_source(modified_tree)
    except Exception as e:
        print(f"❌ Failed to stringify AST for {file_path.name}: {e}")
        return

    # Insert the new import nicely below shebangs or module docstrings
    lines = cleaned_source.splitlines(keepends=True)
    insert_idx = 0

    # Skip past shebang or top-level docstring to preserve structural hygiene
    if lines and lines[0].startswith("#!"):
        insert_idx = 1
    if len(lines) > insert_idx and (
        lines[insert_idx].strip().startswith('"""') or lines[insert_idx].strip().startswith("'''")
    ):
        insert_idx += 1

    lines.insert(insert_idx, import_statement)

    try:
        file_path.write_text("".join(lines), encoding="utf-8")
        print(f"✅ Refactored {file_path.name}: Stripped {objects_to_remove} -> added 'dh' import")
    except Exception as e:
        print(f"❌ Error writing updates back to {file_path.name}: {e}")


def main():
    if not REPEATED_JSON_PATH.exists():
        print(f"Error: {REPEATED_JSON_PATH.name} not found in the current directory.")
        return

    # Create mapping of file names to their duplicated components
    refactor_map = load_refactoring_maps()
    current_dir = Path(".")

    # Gather target executable files present in local execution space
    local_files = {f.name: f for f in current_dir.glob("*.py")}

    tasks = []
    for filename, objects in refactor_map.items():
        if filename in local_files:
            tasks.append((local_files[filename], objects))

    if not tasks:
        print("No matching files found in the current directory to refactor.")
        return

    print(f"🚀 Found {len(tasks)} files to clean structural code from. Starting parallel processing...")

    # Safe Multi-Threaded IO Processing
    with ThreadPoolExecutor() as executor:
        for file_path, objects in tasks:
            executor.submit(refactor_single_file, file_path, objects)

    print("🎉 Structural refactoring complete! All duplicate bodies stripped.")


if __name__ == "__main__":
    main()
