#!/data/data/com.termux/files/usr/bin/env python
import concurrent.futures
import re
from pathlib import Path

# Match single-line comments (//...), multi-line comments (/*...*/),
# and character/string literals ("..." or '...') to avoid false positives.
COMMENT_RE = re.compile(
    r'(?://[^\n]*|/\*.*?\*/)|(?:"(?:\\[\s\S]|[^"\\])*"|\'(?:\\[\s\S]|[^\'\\])*\')',
    re.DOTALL,
)


def strip_comments_from_text(text: str) -> str:
    """Removes C/C++ style comments from a string, preserving string literals."""

    def replacer(match):
        group = match.group(0)
        if group.startswith("/") or group.startswith("/*"):
            # It's a comment. Return empty string (or a newline for block comments
            # if you want to preserve line numbers, but empty string removes it entirely).
            return ""
        # It's a literal string/character, return it untouched
        return group

    return COMMENT_RE.sub(replacer, text)


def process_file(file_path: Path) -> str:
    """Reads, processes, and overwrites a single file in-place."""
    try:
        # Read the file
        content = file_path.read_text(encoding="utf-8", errors="replace")

        # Strip comments
        cleaned_content = strip_comments_from_text(content)

        # Write back in-place if changes were made
        if content != cleaned_content:
            file_path.write_text(cleaned_content, encoding="utf-8")
            return f"Cleaned: {file_path}"
        return f"No comments found: {file_path}"

    except Exception as e:
        return f"Error processing {file_path}: {e}"


def main():
    # Target extensions
    extensions = {".h", ".c", ".cpp", ".hpp"}

    # Recursively find all matching files in the current directory
    current_dir = Path(".")
    files_to_process = [p for p in current_dir.rglob("*") if p.suffix.lower() in extensions]

    if not files_to_process:
        print("No matching C/C++ files found.")
        return

    print(f"Found {len(files_to_process)} files. Processing in parallel...")

    # Process files in parallel using a process pool
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = executor.map(process_file, files_to_process)

        for result in results:
            print(result)


if __name__ == "__main__":
    main()
