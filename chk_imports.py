#!/data/data/com.termux/files/home/.local/bin/python
"""
Find .py files with import statements not at the head of the file.
Ignores imports inside functions.

Usage:
    python check_imports.py [directory] [-a]

Options:
    -a    Autofix: move imports to the top of the file
"""

import ast
import argparse
import sys
from pathlib import Path
from typing import List, Tuple, Optional


def find_imports_not_at_head(file_path: Path) -> List[Tuple[int, int, str]]:
    """
    Find import statements that are not at the head of the file.
    Returns list of (line_number, end_line, import_text) tuples.
    Ignores imports inside functions.
    """
    try:
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"  [SKIP] {file_path}: Could not parse ({e})")
        return []

    # Find the line number where the first non-import, non-comment, non-blank statement starts
    # This is the "head" of the file
    head_end_line = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Import at top level - part of the head
            head_end_line = max(head_end_line, node.end_lineno or node.lineno)
        elif isinstance(node, (ast.Expr, ast.Constant)):
            # Could be docstring or comment - check if it's a docstring
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                # Docstring - part of the head
                head_end_line = max(head_end_line, node.end_lineno or node.lineno)
            else:
                # Other expression - head ends here
                break
        else:
            # First non-import statement - head ends here
            break

    # Find all imports that are NOT at the head and NOT inside functions
    misplaced_imports = []

    for node in ast.walk(tree):
        # Skip imports that are at the head of the file
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if node.lineno <= head_end_line:
                continue

            # Check if this import is inside a function
            if is_inside_function(tree, node):
                continue

            # Get the source text of the import
            lines = source.split('\n')
            import_text = '\n'.join(lines[node.lineno - 1:node.end_lineno])
            misplaced_imports.append((node.lineno, node.end_lineno or node.lineno, import_text))

    return misplaced_imports


def is_inside_function(tree: ast.AST, node: ast.AST) -> bool:
    """Check if a node is inside a function definition."""
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (parent.lineno <= node.lineno <= (parent.end_lineno or parent.lineno)):
                # Check if node is actually a descendant of this function
                for child in ast.walk(parent):
                    if child is node:
                        return True
    return False


def autofix_imports(file_path: Path, misplaced_imports: List[Tuple[int, int, str]]) -> bool:
    """
    Move misplaced imports to the top of the file.
    Returns True if changes were made.
    """
    if not misplaced_imports:
        return False

    source = file_path.read_text(encoding='utf-8')
    lines = source.split('\n')

    # Collect import statements to move
    imports_to_move = []
    for line_num, end_line, import_text in misplaced_imports:
        imports_to_move.append(import_text)

    # Remove the misplaced imports from their current positions
    # Process in reverse order to maintain line numbers
    for line_num, end_line, _ in sorted(misplaced_imports, reverse=True):
        del lines[line_num - 1:end_line]

    # Find where to insert the imports (after module docstring and existing head imports)
    insert_index = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            insert_index = i + 1
        elif stripped.startswith(('"""', "'''")):
            # Check if this is a docstring
            if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                insert_index = i + 1
            else:
                # Multi-line docstring - find its end
                quote_char = '"""' if '"""' in stripped else "'''"
                for j in range(i + 1, len(lines)):
                    if quote_char in lines[j]:
                        insert_index = j + 1
                        break
                break
        elif stripped.startswith(('import ', 'from ')):
            insert_index = i + 1
        else:
            break

    # Insert the imports at the top
    new_lines = lines[:insert_index] + imports_to_move + [''] + lines[insert_index:]

    # Write the modified file
    file_path.write_text('\n'.join(new_lines), encoding='utf-8')
    return True


def process_file(file_path: Path, autofix: bool) -> Tuple[bool, bool]:
    """
    Process a single file.
    Returns (has_issues, was_fixed)
    """
    misplaced = find_imports_not_at_head(file_path)

    if not misplaced:
        return False, False

    print(f"\n{file_path}:")
    for line_num, end_line, import_text in misplaced:
        print(f"  Line {line_num}: {import_text.strip()}")

    if autofix:
        if autofix_imports(file_path, misplaced):
            print(f"  [FIXED] Moved {len(misplaced)} import(s) to top")
            return True, True
        else:
            print(f"  [ERROR] Failed to fix")
            return True, False

    return True, False


def main():
    parser = argparse.ArgumentParser(
        description='Find .py files with imports not at the head of the file'
    )
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Directory to scan (default: current directory)'
    )
    parser.add_argument(
        '-a', '--autofix',
        action='store_true',
        help='Automatically move misplaced imports to the top of the file'
    )

    args = parser.parse_args()

    root = Path(args.directory)
    if not root.exists():
        print(f"Error: Directory '{root}' does not exist")
        sys.exit(1)

    if root.is_file():
        files = [root] if root.suffix == '.py' else []
    else:
        files = list(root.rglob('*.py'))

    if not files:
        print(f"No .py files found in '{root}'")
        return

    print(f"Scanning {len(files)} Python file(s)...")

    files_with_issues = 0
    files_fixed = 0

    for file_path in files:
        has_issues, was_fixed = process_file(file_path, args.autofix)
        if has_issues:
            files_with_issues += 1
        if was_fixed:
            files_fixed += 1

    print(f"\n{'=' * 50}")
    print(f"Summary:")
    print(f"  Files with misplaced imports: {files_with_issues}")
    if args.autofix:
        print(f"  Files fixed: {files_fixed}")
    else:
        print(f"  Run with -a to autofix")

    if files_with_issues > 0 and not args.autofix:
        sys.exit(1)


if __name__ == '__main__':
    main()
