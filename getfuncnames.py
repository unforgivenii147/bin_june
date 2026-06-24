#!/data/data/com.termux/files/usr/bin/python
import ast
import sys


def get_function_names(filename, skip_main=True):
    """
    Extract function names from a Python file.

    Args:
        filename: Path to the Python file
        skip_main: If True, skip functions named 'main'

    Returns:
        List of function names
    """
    try:
        with open(filename, "r") as file:
            tree = ast.parse(file.read())

        function_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if skip_main and node.name == "main":
                    continue
                function_names.append(node.name)

        return function_names

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return []
    except SyntaxError as e:
        print(f"Error: Syntax error in '{filename}': {e}")
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []


if __name__ == "__main__":
    # Check if filename is provided
    if len(sys.argv) < 2:
        print("Usage: python script.py <python_file>")
        sys.exit(1)

    filename = sys.argv[1]

    # Get function names
    functions = get_function_names(filename, skip_main=True)

    # Print results
    if functions:
        print("Functions found (excluding 'main'):")
        for func in functions:
            print(f"  - {func}")
    else:
        print("No functions found (excluding 'main').")
