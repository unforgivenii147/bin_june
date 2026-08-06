#!/data/data/com.termux/files/home/.local/bin/python
import os
import sys
# Dictionary mapping file extensions to their respective comment characters
EXTENSION_COMMENTS = {
    ".py": "#",
    ".sh": "#",
    ".yaml": "#",
    ".yml": "#",
    ".rb": "#",
    ".js": "//",
    ".ts": "//",
    ".cpp": "//",
    ".c": "//",
    ".java": "//",
    ".go": "//",
    ".html": "<!--",  # Note: HTML requires closing, but using standard prefix placement here
    ".css": "/*",
}
def main():
    # 1. Validate that enough arguments were passed
    if len(sys.argv) < 4:
        print("Error: Missing arguments.\nUsage: python comment_range.py <filename> <start_line> <end_line>")
        sys.exit(1)
    # 2. Extract inputs from sys.argv[1:]
    filepath = sys.argv[1]
    try:
        start_line = int(sys.argv[2])
        end_line = int(sys.argv[3])
    except ValueError:
        print("Error: Start and end lines must be valid integers.")
        sys.exit(1)
    # 3. Basic validation of user logic
    if start_line < 1 or end_line < start_line:
        print("Error: Line numbers must start from 1, and end line must be >= start line.")
        sys.exit(1)
    # 4. Check if the target file actually exists
    if not os.path.exists(filepath):
        print(f"Error: The file '{filepath}' does not exist.")
        sys.exit(1)
    # 5. Detect the correct comment character based on file extension
    _, ext = os.path.splitext(filepath.lower())
    comment_char = EXTENSION_COMMENTS.get(ext, "#")  # Defaults to '#' if extension is unknown
    # 6. Read the existing contents of the file
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    # 7. Safety check: Ensure the requested line range exists in the file
    total_lines = len(lines)
    if start_line > total_lines:
        print(f"Error: Start line ({start_line}) exceeds file length ({total_lines} lines).")
        sys.exit(1)
    # Adjust end_line if it exceeds the maximum lines in the file
    actual_end = min(end_line, total_lines)
    # 8. Loop through and modify the lines in memory (1-based to 0-based conversion)
    for i in range(start_line - 1, actual_end):
        # Only add a comment if the line isn't already commented out
        if not lines[i].strip().startswith(comment_char):
            # Special case styling handling for CSS/HTML block structures if desired,
            # but keeping it simple by just prefixing the line here.
            lines[i] = f"{comment_char} {lines[i]}"
    # 9. Update the file in place by overwriting it
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Success: Commented out lines {start_line} to {actual_end} in '{filepath}' using '{comment_char}'.")
if __name__ == "__main__":
    main()
