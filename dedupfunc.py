#!/data/data/com.termux/files/usr/bin/python

"""
Duplicate Function Detector and Remover
Detects functions with identical bodies (ignoring whitespace and comments)
and optionally removes duplicates with user confirmation.
"""

import argparse
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


class FunctionInfo:
    """Store information about a function"""

    def __init__(self, name: str, body: str, lineno: int, node: ast.FunctionDef) -> None:
        self.name = name
        self.body = self._normalize_body(body)
        self.original_body = body
        self.lineno = lineno
        self.node = node

    @staticmethod
    def _normalize_body(body: str) -> str:
        """Normalize function body by removing comments and extra whitespace"""
        # Remove comments
        lines = []
        for line in body.split("\n"):
            # Remove inline comments but keep strings that might contain '#'
            line_without_comments = re.sub(r'(?<!["\'])#.*$', "", line)
            lines.append(line_without_comments)

        # Join and normalize whitespace
        body = "\n".join(lines)
        # Remove empty lines and strip each line
        lines = [line.strip() for line in body.split("\n") if line.strip()]
        return "\n".join(lines)


class DuplicateFunctionFinder(ast.NodeVisitor):
    """AST visitor to find functions and extract their bodies"""

    def __init__(self) -> None:
        self.functions: List[FunctionInfo] = []
        self.source_lines: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract function information"""
        # Get the function body as source code
        body_start = node.body[0].lineno - 1
        body_end = node.body[-1].end_lineno

        # Extract the source code for the function body
        body_lines = self.source_lines[body_start:body_end]
        body_code = "\n".join(body_lines)

        func_info = FunctionInfo(name=node.name, body=body_code, lineno=node.lineno, node=node)
        self.functions.append(func_info)

        self.generic_visit(node)

    def analyze_file(self, filepath: str) -> Dict[str, List[FunctionInfo]]:
        """Analyze a Python file and return duplicate groups"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            self.source_lines = content.splitlines()

        try:
            tree = ast.parse(content)
            self.visit(tree)
        except SyntaxError as e:
            print(f"Syntax error in file: {e}")
            return {}

        # Group functions by their normalized body
        groups = defaultdict(list)
        for func in self.functions:
            groups[func.body].append(func)

        # Only return groups with more than one function
        return {body: funcs for body, funcs in groups.items() if len(funcs) > 1}


class DuplicateFunctionRemover:
    """Handle removal of duplicate functions"""

    def __init__(self, filepath: str) -> None:
        self.filepath = Path(filepath)
        self.content = None
        self.lines = None

    def _get_function_lines(self, func_info: FunctionInfo) -> Tuple[int, int]:
        """Get start and end line numbers for a function"""
        node = func_info.node

        # Find the end line (including decorators)
        end_line = node.end_lineno if hasattr(node, "end_lineno") else node.lineno

        # If there are decorators, include them
        if node.decorator_list:
            start_line = node.decorator_list[0].lineno
        else:
            start_line = node.lineno

        return start_line, end_line

    def _extract_function_code(self, func_info: FunctionInfo) -> str:
        """Extract the complete function code including decorators"""
        start_line, end_line = self._get_function_lines(func_info)
        return "\n".join(self.lines[start_line - 1 : end_line])

    def remove_duplicates(self, groups: Dict[str, List[FunctionInfo]], keep_choice: Dict[str, int]) -> bool:
        """Remove duplicate functions based on user choices"""
        # Load the file content
        with open(self.filepath, "r", encoding="utf-8") as f:
            self.content = f.read()
            self.lines = self.content.splitlines()

        # Collect lines to remove
        lines_to_remove = set()
        functions_to_remove = []

        for body, funcs in groups.items():
            keep_index = keep_choice.get(body, 0)

            # Remove all functions except the one to keep
            for i, func in enumerate(funcs):
                if i != keep_index:
                    start_line, end_line = self._get_function_lines(func)
                    for line_num in range(start_line - 1, end_line):
                        lines_to_remove.add(line_num)
                    functions_to_remove.append(func)

        # Remove the lines (from bottom to top to preserve line numbers)
        new_lines = []
        for i, line in enumerate(self.lines):
            if i not in lines_to_remove:
                new_lines.append(line)

        # Write back to file
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines))
            return True
        except Exception as e:
            print(f"Error writing to file: {e}")
            return False

    def backup_file(self) -> str:
        """Create a backup of the original file"""
        backup_path = self.filepath.with_suffix(self.filepath.suffix + ".backup")
        with open(self.filepath, "r", encoding="utf-8") as src:
            with open(backup_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
        return str(backup_path)


def display_duplicates(groups: Dict[str, List[FunctionInfo]]) -> bool:
    """Display duplicate function groups to the user"""
    if not groups:
        print("No duplicate functions found!")
        return False

    print("\n" + "=" * 80)
    print("DUPLICATE FUNCTIONS FOUND")
    print("=" * 80)

    for idx, (body, funcs) in enumerate(groups.items(), 1):
        print(f"\nGroup {idx}:")
        print(f"  Body hash: {hash(body)}")
        print(f"  {len(funcs)} functions with identical body:")

        for i, func in enumerate(funcs, 1):
            print(f"    {i}. '{func.name}' (line {func.lineno})")

        # Show a preview of the function body
        body_preview = body[:150] + "..." if len(body) > 150 else body
        print(f"\n  Body preview:\n{body_preview}")
        print("-" * 40)

    return True


def get_user_choices(groups: Dict[str, List[FunctionInfo]]) -> Dict[str, int]:
    """Get user choices for which function to keep in each group"""
    choices = {}

    for body, funcs in groups.items():
        print(f"\nGroup with {len(funcs)} duplicate functions:")
        for i, func in enumerate(funcs):
            print(f"  [{i}] Keep '{func.name}' (line {func.lineno})")

        while True:
            try:
                choice = input(f"Which function to keep? [0-{len(funcs) - 1}]: ")
                choice_num = int(choice)
                if 0 <= choice_num < len(funcs):
                    choices[body] = choice_num
                    break
                else:
                    print(f"Please enter a number between 0 and {len(funcs) - 1}")
            except ValueError:
                print("Please enter a valid number")

    return choices


def main() -> None:
    parser = argparse.ArgumentParser(description="Find and optionally remove duplicate functions in Python files")
    parser.add_argument("file", help="Python file to analyze")
    parser.add_argument("-r", "--remove", action="store_true", help="Remove duplicate functions with user confirmation")
    parser.add_argument("--backup", action="store_true", help="Create a backup before removing (implies -r)")

    args = parser.parse_args()

    filepath = args.file

    # Check if file exists
    if not Path(filepath).exists():
        print(f"Error: File '{filepath}' not found")
        sys.exit(1)

    # Check if it's a Python file
    if not filepath.endswith(".py"):
        print(f"Warning: File '{filepath}' does not have .py extension")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            sys.exit(0)

    # Find duplicate functions
    print(f"Analyzing {filepath}...")
    finder = DuplicateFunctionFinder()
    duplicates = finder.analyze_file(filepath)

    if not display_duplicates(duplicates):
        sys.exit(0)

    # Handle removal if requested
    if args.remove or args.backup:
        remover = DuplicateFunctionRemover(filepath)

        # Create backup if requested
        if args.backup:
            backup_path = remover.backup_file()
            print(f"\nBackup created at: {backup_path}")

        # Get user choices
        print("\n" + "=" * 80)
        print("SELECT FUNCTIONS TO KEEP")
        print("=" * 80)
        choices = get_user_choices(duplicates)

        # Confirm removal
        print("\n" + "=" * 80)
        confirm = input("Proceed with removing duplicate functions? (y/N): ")

        if confirm.lower() == "y":
            if remover.remove_duplicates(duplicates, choices):
                print("✓ Duplicate functions removed successfully!")
            else:
                print("✗ Failed to remove duplicates")
                sys.exit(1)
        else:
            print("Operation cancelled")
            sys.exit(0)
    else:
        print("\nUse -r or --remove to remove duplicates with user confirmation")


if __name__ == "__main__":
    main()
