#!/data/data/com.termux/files/usr/bin/python

import argparse
import ast
import multiprocessing as mp
import shutil
import traceback
from pathlib import Path


def find_unused_functions(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ([], ["SyntaxError while parsing file"])
    defined = set()
    called = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            defined.add(node.name)
            self.generic_visit(node)

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            self.generic_visit(node)

    Visitor().visit(tree)
    unused = defined - called
    return (list(unused), [])


def remove_functions_from_source(source, unused_functions):
    tree = ast.parse(source)
    new_body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in unused_functions:
            continue
        new_body.append(node)
    tree.body = new_body
    return ast.unparse(tree)


def process_file(filepath, dry_run=False):
    errors = []
    filepath = Path(filepath)
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return (filepath, [], [f"Error reading file: {e}"])
    unused, parse_errors = find_unused_functions(source)
    errors.extend(parse_errors)
    if not unused:
        return (filepath, [], errors)
    try:
        new_source = remove_functions_from_source(source, unused)
    except Exception:
        errors.append("Error rewriting file:\n" + traceback.format_exc())
        return (filepath, unused, errors)
    if not dry_run:
        backup_path = filepath.with_suffix(filepath.suffix + ".bak")
        shutil.copy2(filepath, backup_path)
        filepath.write_text(new_source, encoding="utf-8")
    return (filepath, unused, errors)


def gather_python_files(root: Path):
    return [p for p in root.rglob("*.py") if p.is_file()]


def worker(args):
    return process_file(*args)


def main():
    parser = argparse.ArgumentParser(description="Remove unused functions recursively.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without modifying files.")
    parser.add_argument("--workers", type=int, default=mp.cpu_count(), help="Number of processes")
    args = parser.parse_args()
    root = Path()
    py_files = gather_python_files(root)
    print(f"Scanning {len(py_files)} Python files...")
    with mp.Pool(args.workers) as pool:
        results = pool.map(worker, [(f, args.dry_run) for f in py_files])
    print("\n=== RESULTS ===")
    for filepath, unused, errors in results:
        if unused:
            if args.dry_run:
                print(f"[DRY-RUN] Would remove {unused} from {filepath}")
            else:
                print(f"Removed {unused} from {filepath} (backup created)")
        for err in errors:
            print(f"[ERROR] {filepath}: {err}")


if __name__ == "__main__":
    main()
