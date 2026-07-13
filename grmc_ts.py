#!/data/data/com.termux/files/usr/bin/env python
import argparse
import ast
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

# Initialize Tree-Sitter Language and Parser
PY_LANGUAGE = Language(tspython.language())


def get_parser() -> Parser:
    parser = Parser(PY_LANGUAGE)
    return parser


def should_preserve_comment(comment_bytes: bytes) -> bool:
    """Check if the comment is a shebang, type hint, or formatting directive."""
    text = comment_bytes.decode("utf-8", errors="ignore").strip()
    return (
        text.startswith("#!")
        or text.startswith("# type:")
        or text.startswith("# fmt:")
        or text == "# fmt: skip"
        or text == "# fmt: on"
        or text == "# fmt: off"
    )


def process_file(file_path: Path) -> str:
    """Processes a single python file to remove comments and non-module docstrings."""
    try:
        source_bytes = file_path.read_bytes()
    except Exception as e:
        return f"[ERROR] Failed to read {file_path}: {e}"

    parser = get_parser()
    tree = parser.parse(source_bytes)
    root = tree.root_node

    # Step 1: Identify all comments and docstring candidates
    removals = []  # List of tuples: (start_byte, end_byte, replacement_bytes)
    module_docstring_node = None

    # Check if the very first expression statement in the module is a docstring
    if root.child_count > 0:
        first_child = root.child(0)
        if first_child.type == "expression_statement":
            expr_child = first_child.child(0)
            if expr_child and expr_child.type == "string":
                module_docstring_node = first_child

    # Traverse using TreeCursor for optimal memory and lookup performance
    cursor = tree.walk()
    reached_end = False

    while not reached_end:
        node = cursor.node

        # Identify comments
        if node.type == "comment":
            node_bytes = source_bytes[node.start_byte : node.end_byte]
            if not should_preserve_comment(node_bytes):
                removals.append((node.start_byte, node.end_byte, b""))

        # Identify docstrings inside expression statements (excluding module docstring)
        elif node.type == "expression_statement" and node != module_docstring_node:
            expr_child = node.child(0)
            if expr_child and expr_child.type == "string":
                # Check if it's within a function or class body block
                parent = node.parent
                if parent and parent.type == "block":
                    # If this docstring is the ONLY statement in the block, replace with 'pass'
                    if parent.named_child_count == 1:
                        removals.append((node.start_byte, node.end_byte, b"pass"))
                    else:
                        removals.append((node.start_byte, node.end_byte, b""))

        # Standard tree cursor traversal architecture
        if cursor.goto_first_child():
            continue
        if cursor.goto_next_sibling():
            continue

        # Backtrack upwards until a sibling can be found
        while True:
            if not cursor.goto_parent():
                reached_end = True
                break
            if cursor.goto_next_sibling():
                break

    if not removals:
        return f"[SKIPPED] No structural modifications needed for {file_path}"

    # Step 2: Apply modifications from end to beginning to maintain offset alignment
    removals.sort(key=lambda x: x[0], reverse=True)

    modified_bytes = bytearray(source_bytes)
    for start, end, replacement in removals:
        modified_bytes[start:end] = replacement

    final_code = bytes(modified_bytes)

    # Step 3: Structural Validation via AST check before commitment
    try:
        ast.parse(final_code, filename=str(file_path))
    except SyntaxError as e:
        return f"[WARNING] Validation failed for {file_path} (Changes rejected): {e}"

    # Step 4: Write-back safe modifications inplace
    try:
        file_path.write_bytes(final_code)
        return f"[SUCCESS] Processed and stripped: {file_path}"
    except Exception as e:
        return f"[ERROR] Failed to save updates to {file_path}: {e}"


def gather_files(inputs) -> list[Path]:
    """Finds target py files based on initial execution directives."""
    files = []
    if not inputs:
        # Default recursive lookup from execution origin point
        return list(Path(".").rglob("*.py"))

    for item in inputs:
        p = Path(item)
        if p.is_file() and p.suffix == ".py":
            files.append(p)
        elif p.is_dir():
            files.extend(p.rglob("*.py"))
    return files


def main():
    parser = argparse.ArgumentParser(description="Strip comments and docstrings using Tree-Sitter safely.")
    parser.add_argument("paths", nargs="*", help="Target files or directories to process. Defaults to '.' if empty.")
    args = parser.parse_args()

    targets = gather_files(args.paths)
    if not targets:
        print("No target Python source files detected.")
        sys.exit(0)

    print(f"Queue loaded. Processing {len(targets)} target files via Parallel Pipeline...")

    # Execute utilizing Process Pool worker bounds to counter GIL locks
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(process_file, target): target for target in targets}
        for future in as_completed(futures):
            result_string = future.result()
            print(result_string)


if __name__ == "__main__":
    main()
