#!/data/data/com.termux/files/usr/bin/python
import ast
import hashlib
import sys
from pathlib import Path


def get_function_content_hash(function_node):
    """
    Calculate hash of function content (excluding function name and decorators).
    This ensures we match functions by their implementation, not just name.
    """
    # Create a copy of the function node without the name
    # We want to hash the function body, arguments, and return type
    func_copy = ast.FunctionDef(
        name="_temp",  # placeholder name
        args=function_node.args,
        body=function_node.body,
        decorator_list=[],
        returns=function_node.returns,
        type_comment=function_node.type_comment,
    )

    # Convert to source code and hash
    try:
        import astunparse

        source = astunparse.unparse(func_copy)
    except ImportError:
        # Fallback: use the original source if astunparse not available
        try:
            source = ast.get_source_segment(open(function_node.lineno, "r").read(), function_node)
        except:
            source = str(ast.dump(func_copy))

    return hashlib.md5(source.encode("utf-8")).hexdigest()


def get_function_content_hash_manual(filename, function_node):
    """
    Alternative method: extract function content by line numbers.
    More reliable for older Python versions.
    """
    try:
        with open(filename, "r") as f:
            lines = f.readlines()

        # Get function source lines
        start_line = function_node.lineno - 1
        end_line = function_node.end_lineno

        # Extract the function body (excluding the function definition line)
        func_lines = lines[start_line:end_line]

        # Skip the function definition line and decorators
        body_start = 1
        for i, line in enumerate(func_lines):
            if line.strip() and not line.strip().startswith("@"):
                # Found the actual function definition
                # For multi-line function definitions, find the colon
                if ":" in line:
                    body_start = i + 1
                    break

        # Extract just the body (indentation preserved)
        body_lines = func_lines[body_start:]

        # Normalize by stripping leading whitespace from each line
        if body_lines:
            min_indent = min(len(line) - len(line.lstrip()) for line in body_lines if line.strip())
            normalized_body = "\n".join(line[min_indent:] if line.strip() else line for line in body_lines)
        else:
            normalized_body = ""

        # Include function signature (without name) and body
        signature = f"args={ast.dump(function_node.args)}"
        if function_node.returns:
            signature += f"returns={ast.dump(function_node.returns)}"

        content = signature + normalized_body
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    except Exception as e:
        print(f"⚠️  Warning: Could not extract content for {function_node.name}: {e}")
        return None


def extract_functions_with_hash(filename):
    """
    Extract functions from a Python file with their content hashes.
    """
    try:
        with open(filename, "r") as file:
            tree = ast.parse(file.read())

        functions = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                content_hash = get_function_content_hash_manual(filename, node)
                if content_hash:
                    functions[node.name] = {
                        "node": node,
                        "hash": content_hash,
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                    }

        return functions

    except SyntaxError as e:
        print(f"❌ Syntax error in '{filename}': {e}")
        return None
    except Exception as e:
        print(f"❌ Error reading '{filename}': {e}")
        return None


def remove_functions_from_file(file1, file2):
    """
    Remove functions from file2 that have matching content hash in file1.
    """
    print(f"📖 Reading functions from {file1}...")
    functions1 = extract_functions_with_hash(file1)
    if functions1 is None:
        return False

    print(f"📖 Reading functions from {file2}...")
    functions2 = extract_functions_with_hash(file2)
    if functions2 is None:
        return False

    # Find functions to remove (matching content hash)
    hashes1 = {info["hash"] for info in functions1.values()}
    functions_to_remove = []

    for func_name, func_info in functions2.items():
        if func_info["hash"] in hashes1:
            functions_to_remove.append(func_info)
            print(f"  🗑️  Marked for removal: {func_name} (matches content in {file1})")

    if not functions_to_remove:
        print("✅ No duplicate functions found. No changes needed.")
        return True

    # Sort by line number in reverse order to preserve line numbers when removing
    functions_to_remove.sort(key=lambda x: x["lineno"], reverse=True)

    # Read file2 content
    try:
        with open(file2, "r") as f:
            lines = f.readlines()

        # Remove function blocks
        for func_info in functions_to_remove:
            start = func_info["lineno"] - 1
            end = func_info["end_lineno"]

            # Also remove preceding decorators
            while start > 0:
                prev_line = lines[start - 1].strip()
                if prev_line.startswith("@") or prev_line.strip() == "":
                    start -= 1
                else:
                    break

            # Remove the lines
            del lines[start:end]
            print(f"  ✂️  Removed function {func_info['node'].name} (lines {start + 1}-{end})")

        # Write back to file
        with open(file2, "w") as f:
            f.writelines(lines)

        print(f"✅ Successfully updated {file2} in-place")
        return True

    except Exception as e:
        print(f"❌ Error updating {file2}: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python remove_duplicate_functions.py <file1.py> <file2.py>")
        print("  Removes functions from file2.py that exist in file1.py (based on content hash)")
        sys.exit(1)

    file1 = sys.argv[1]
    file2 = sys.argv[2]

    # Check if files exist
    if not Path(file1).exists():
        print(f"❌ Error: '{file1}' not found.")
        sys.exit(1)

    if not Path(file2).exists():
        print(f"❌ Error: '{file2}' not found.")
        sys.exit(1)

    print(f"🔍 Comparing functions between:")
    print(f"   File 1: {file1}")
    print(f"   File 2: {file2}")
    print("-" * 50)

    success = remove_functions_from_file(file1, file2)
    sys.exit(0 if success else 1)
