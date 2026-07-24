#!/data/data/com.termux/files/home/.local/bin/python
import argparse
import ast
import concurrent.futures
import os
import sys
from collections import defaultdict
from pathlib import Path

# --- Worker Functions (Parallel execution) ---


def parse_file_definitions(file_path: Path) -> dict:
    """
    Parses a single file to extract its function, class, and constant definitions.
    Returns a dictionary mapping a canonical identifier (type, name, structural code)
    to the source code structure.
    """
    definitions = {}
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except Exception:
        # Skip files with syntax errors or unreadable files
        return {}

    for node in tree.body:
        # 1. Functions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node_key = ("function", node.name, ast.unparse(node))
            definitions[node_key] = {"name": node.name, "type": "function", "node": node}

        # 2. Classes
        elif isinstance(node, ast.ClassDef):
            node_key = ("class", node.name, ast.unparse(node))
            definitions[node_key] = {"name": node.name, "type": "class", "node": node}

        # 3. Global Constants (Top-level Assign with simple Target uppercase/all-caps or plain names)
        elif isinstance(node, ast.Assign):
            # Check if it targets a simple name (e.g., CONSTANT_NAME = value)
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                # Track top-level constants
                node_key = ("constant", name, ast.unparse(node))
                definitions[node_key] = {"name": name, "type": "constant", "node": node}

    return {node_key: (str(file_path), data) for node_key, data in definitions.items()}


def modify_affected_file(file_path_str: str, obj_name: str, obj_type: str, raw_obj_code: str) -> str:
    """
    Removes the duplicate definition from an affected file and injects the import statement.
    Validates with ast.parse before returning the modified code string.
    """
    file_path = Path(file_path_str)
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    new_body = []
    removed = False

    for node in tree.body:
        # Check matching function or class
        if obj_type in ("function", "class") and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            if node.name == obj_name and ast.unparse(node) == raw_obj_code:
                removed = True
                continue  # Exclude the node

        # Check matching constant
        elif obj_type == "constant" and isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == obj_name and ast.unparse(node) == raw_obj_code:
                    removed = True
                    continue  # Exclude the node

        new_body.append(node)

    if not removed:
        return source  # Code wasn't changed

    # Inject: from dh import obj_name
    import_node = ast.ImportFrom(module="dh", names=[ast.alias(name=obj_name, asname=None)], level=0)
    new_body.insert(0, import_node)

    # Reconstruct AST
    tree.body = new_body
    modified_source = ast.unparse(tree)

    # Critical Validation Step
    ast.parse(modified_source)
    return modified_source


# --- Main Management Logic ---


def main():
    parser = argparse.ArgumentParser(
        description="Recursively find and consolidate duplicate functions, classes, and constants."
    )
    parser.add_argument(
        "-m",
        "--move",
        action="store_true",
        help="Consolidate duplicate code blocks into dh.py and update files with required imports.",
    )
    args = parser.parse_args()

    current_dir = Path(".")
    dh_path = current_dir / "dh.py"
    script_path = Path(__file__).resolve()

    # Find all Python files recursively
    py_files = [f for f in current_dir.rglob("*.py") if f.resolve() != script_path and f.resolve() != dh_path.resolve()]

    if not py_files:
        print("🔍 No Python files found to scan.")
        return

    print(f"🔍 Scanning {len(py_files)} files concurrently...")

    # Global map to store instances of code structures
    # Key: (type, name, unparsed_code_hashable) -> List of (file_path_str, node_data)
    global_registry = defaultdict(list)

    cpu_cores = os.cpu_count() or 1
    with concurrent.futures.ProcessPoolExecutor(max_workers=cpu_cores) as executor:
        futures = {executor.submit(parse_file_definitions, f): f for f in py_files}
        for future in concurrent.futures.as_completed(futures):
            file_defs = future.result()
            for node_key, (file_path_str, data) in file_defs.items():
                global_registry[node_key].append((file_path_str, data))

    # Isolate actual duplicates (appear in more than 1 file)
    duplicates = {k: v for k, v in global_registry.items() if len(v) > 1}

    if not duplicates:
        print("🎉 Success! No repeated functions, classes, or constants were detected.")
        return

    print(f"⚠️  Detected {len(duplicates)} repeated structural definitions:\n")

    dh_additions = []
    files_to_update = defaultdict(list)  # file_path -> list of objects to extract

    for (obj_type, obj_name, raw_code), occurrences in duplicates.items():
        files_listed = [occ[0] for occ in occurrences]
        print(f"[{obj_type.upper()}] '{obj_name}' is repeated in {len(files_listed)} files:")
        for f in files_listed:
            print(f"   -> {f}")
        print()

        if args.move:
            dh_additions.append(raw_code)
            for f_str, _ in occurrences:
                files_to_update[f_str].append((obj_name, obj_type, raw_code))

    # Handle the refactoring flag (-m)
    if args.move:
        print("🛠️  Processing Consolidation (-m flag active)...")

        # 1. Update or generate dh.py safely
        existing_dh_content = ""
        if dh_path.exists():
            existing_dh_content = dh_path.read_text(encoding="utf-8")

        new_dh_content = existing_dh_content + "\n\n" + "\n\n".join(dh_additions)

        try:
            # Validate generated dh.py syntax tree
            ast.parse(new_dh_content)
            dh_path.write_text(new_dh_content, encoding="utf-8")
            print(f"✅ Extracted duplicate definitions safely written to: {dh_path}")
        except Exception as e:
            print(f"❌ Aborted: Merged definitions inside dh.py failed AST parsing logic: {e}")
            sys.exit(1)

        # 2. Update affected code layers in place
        updated_count = 0
        for file_str, objects in files_to_update.items():
            try:
                current_file_path = Path(file_str)
                updated_source = current_file_path.read_text(encoding="utf-8")

                # Progressively drop duplicates and construct imports sequentially
                for obj_name, obj_type, raw_code in objects:
                    updated_source = modify_affected_file(file_str, obj_name, obj_type, raw_code)

                # Write the confirmed structure to disk
                current_file_path.write_text(updated_source, encoding="utf-8")
                print(f"✅ In-place code updated & verified: {file_str}")
                updated_count += 1
            except Exception as e:
                print(f"❌ Failed to parse or modify file safely {file_str}: {e}. Skipping structural changes.")

        print(f"\n📊 Refactor complete. Adjusted and verified {updated_count} files.")


if __name__ == "__main__":
    main()
