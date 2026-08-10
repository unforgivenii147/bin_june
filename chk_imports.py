#!/data/data/com.termux/files/home/.local/bin/python
"""
Find .py files with import statements not at the head of the file.
Ignores imports inside functions.
Usage:
    python check_imports.py [directory] [-a] [-o OUTPUT]
Options:
    -a         Autofix: move imports to the top of the file
    -o OUTPUT  Save report to OUTPUT file (default: errors.txt when not using -a)
"""

import argparse
import ast
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


def find_imports_not_at_head(file_path: Path) -> List[Tuple[int, int, str]]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"  [SKIP] {file_path}: Could not parse ({e})")
        return []
    head_end_line = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            head_end_line = max(head_end_line, node.end_lineno or node.lineno)
        elif isinstance(node, (ast.Expr, ast.Constant)):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                head_end_line = max(head_end_line, node.end_lineno or node.lineno)
            else:
                break
        else:
            break
    misplaced_imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if node.lineno <= head_end_line:
                continue
            if is_inside_function(tree, node):
                continue
            lines = source.split("\n")
            import_text = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            misplaced_imports.append((node.lineno, node.end_lineno or node.lineno, import_text))
    return misplaced_imports


def is_inside_function(tree: ast.AST, node: ast.AST) -> bool:
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if parent.lineno <= node.lineno <= (parent.end_lineno or parent.lineno):
                for child in ast.walk(parent):
                    if child is node:
                        return True
    return False


def autofix_imports(file_path: Path, misplaced_imports: List[Tuple[int, int, str]]) -> bool:
    if not misplaced_imports:
        return False
    source = file_path.read_text(encoding="utf-8")
    lines = source.split("\n")
    imports_to_move = []
    for line_num, end_line, import_text in misplaced_imports:
        imports_to_move.append(import_text)
    for line_num, end_line, _ in sorted(misplaced_imports, reverse=True):
        del lines[line_num - 1 : end_line]
    insert_index = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            insert_index = i + 1
        elif stripped.startswith(('"""', "'''")):
            if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                insert_index = i + 1
            else:
                quote_char = '"""' if '"""' in stripped else "'''"
                for j in range(i + 1, len(lines)):
                    if quote_char in lines[j]:
                        insert_index = j + 1
                        break
                break
        elif stripped.startswith(("import ", "from ")):
            insert_index = i + 1
        else:
            break
    new_lines = lines[:insert_index] + imports_to_move + [""] + lines[insert_index:]
    file_path.write_text("\n".join(new_lines), encoding="utf-8")
    return True


def process_file(file_path: Path, autofix: bool) -> Tuple[bool, bool, List[str]]:
    misplaced = find_imports_not_at_head(file_path)
    if not misplaced:
        return False, False, []

    details = []
    for line_num, end_line, import_text in misplaced:
        detail = f"  Line {line_num}: {import_text.strip()}"
        print(detail)
        details.append(detail)

    if autofix:
        if autofix_imports(file_path, misplaced):
            msg = f"  [FIXED] Moved {len(misplaced)} import(s) to top"
            print(msg)
            details.append(msg)
            return True, True, details
        else:
            msg = f"  [ERROR] Failed to fix"
            print(msg)
            details.append(msg)
            return True, False, details
    return True, False, details


def save_report(report_data: List[Tuple[Path, List[str]]], output_file: str, autofix: bool):
    """Save the report to a file."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Import Check Report\n")
        f.write(f"{'=' * 80}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Mode: {'Autofix' if autofix else 'Check only'}\n")
        f.write(f"{'=' * 80}\n\n")

        if not report_data:
            f.write("No misplaced imports found! All files are clean.\n")
            return

        f.write(f"Files with misplaced imports: {len(report_data)}\n")
        f.write(f"{'-' * 80}\n\n")

        for file_path, details in report_data:
            f.write(f"File: {file_path}\n")
            f.write(f"{'-' * 40}\n")
            for detail in details:
                f.write(f"{detail}\n")
            f.write("\n")

        # Summary statistics
        f.write(f"{'=' * 80}\n")
        f.write(f"Summary:\n")
        f.write(f"  Total files with issues: {len(report_data)}\n")
        total_imports = sum(len([d for d in details if d.startswith("  Line ")]) for _, details in report_data)
        f.write(f"  Total misplaced imports: {total_imports}\n")
        if autofix:
            fixed = sum(1 for _, details in report_data if any("[FIXED]" in d for d in details))
            f.write(f"  Files fixed: {fixed}\n")
            f.write(f"  Files with errors: {len(report_data) - fixed}\n")


def main():
    parser = argparse.ArgumentParser(description="Find .py files with imports not at the head of the file")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument(
        "-a", "--autofix", action="store_true", help="Automatically move misplaced imports to the top of the file"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Save report to file (default: errors.txt when not using -a, no file when using -a unless specified)",
    )
    args = parser.parse_args()

    # Determine output file
    if args.output:
        output_file = args.output
    elif not args.autofix:
        output_file = "errors.txt"
    else:
        output_file = None

    root = Path(args.directory)
    if not root.exists():
        print(f"Error: Directory '{root}' does not exist")
        sys.exit(1)

    if root.is_file():
        files = [root] if root.suffix == ".py" else []
    else:
        files = list(root.rglob("*.py"))

    if not files:
        print(f"No .py files found in '{root}'")
        return

    print(f"Scanning {len(files)} Python file(s)...")

    files_with_issues = 0
    files_fixed = 0
    report_data = []

    for file_path in files:
        has_issues, was_fixed, details = process_file(file_path, args.autofix)
        if has_issues:
            files_with_issues += 1
            report_data.append((file_path, details))
        if was_fixed:
            files_fixed += 1

    print(f"\n{'=' * 50}")
    print(f"Summary:")
    print(f"  Files with misplaced imports: {files_with_issues}")
    if args.autofix:
        print(f"  Files fixed: {files_fixed}")
    else:
        print(f"  Run with -a to autofix")

    # Save report
    if output_file and (files_with_issues > 0 or args.output):
        save_report(report_data, output_file, args.autofix)
        print(f"  Report saved to: {output_file}")

    if files_with_issues > 0 and not args.autofix:
        sys.exit(1)


if __name__ == "__main__":
    main()
