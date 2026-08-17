#!/data/data/com.termux/files/home/.local/bin/python
"""
Script to create directory tree structure from a tree.txt file.
Reads a tree structure and creates the corresponding folders and files.
Usage: python create_tree.py [tree_file]
       (defaults to 'tree.txt' if no argument is provided)
"""
import sys
import re
from pathlib import Path
def parse_tree_file(filename):
    """Parse the tree file and extract file/directory paths."""
    paths = []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    # Stack to keep track of current path depth
    path_stack = []
    prev_depth = -1
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
        # Calculate depth based on tree characters
        # Count the number of tree structure characters (├, └, │, space)
        depth = 0
        for char in line:
            if char in ("│", " ", "\t"):
                depth += 1
            else:
                break
        # Alternative depth calculation based on indentation
        # Each level typically uses 4 spaces or 3 spaces + ├/└
        indentation = len(line) - len(line.lstrip(" │├└─"))
        depth = indentation // 4 if indentation > 0 else 0
        # Extract the actual name from the line
        # Remove tree characters and whitespace
        clean_line = line.strip()
        clean_line = re.sub(r"^[├└─]+\s*", "", clean_line)
        clean_line = re.sub(r"^│\s*", "", clean_line)
        # Skip if line is just tree structure
        if not clean_line or clean_line in ("├──", "└──", "│"):
            continue
        # Remove trailing slash if present (to identify directories)
        is_directory = clean_line.endswith("/")
        name = clean_line.rstrip("/")
        # Skip root directory if it ends with /
        if depth == 0 and is_directory:
            continue
        # Adjust path stack based on depth
        while len(path_stack) > depth:
            path_stack.pop()
        if path_stack:
            parent_path = path_stack[-1] if len(path_stack) > depth else Path(*path_stack[:depth])
        else:
            parent_path = Path(".")
        # Create the full path
        current_path = parent_path / name
        paths.append((current_path, is_directory))
        # Add to stack for future reference
        if is_directory:
            if len(path_stack) <= depth:
                path_stack.append(current_path)
            else:
                path_stack[depth] = current_path
    return paths
def create_tree(paths):
    """Create directories and files based on parsed paths."""
    created_dirs = 0
    created_files = 0
    for path, is_directory in paths:
        try:
            if is_directory:
                # Create directory
                path.mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {path}")
                created_dirs += 1
            else:
                # Create file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch(exist_ok=True)
                print(f"Created file: {path}")
                created_files += 1
        except Exception as e:
            print(f"Error creating {path}: {e}")
    return created_dirs, created_files
def main():
    # Get input file from command line argument or default to 'tree.txt'
    input_file = sys.argv[1] if len(sys.argv) > 1 else "tree.txt"
    print(f"Reading tree structure from: {input_file}")
    print("-" * 50)
    # Parse the tree file
    paths = parse_tree_file(input_file)
    if not paths:
        print("No valid paths found in the tree file.")
        sys.exit(1)
    # Create the tree structure
    created_dirs, created_files = create_tree(paths)
    print("-" * 50)
    print(f"Summary:")
    print(f"  Directories created: {created_dirs}")
    print(f"  Files created: {created_files}")
    print(f"  Total items: {created_dirs + created_files}")
if __name__ == "__main__":
    main()
