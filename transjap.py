#!/data/data/com.termux/files/usr/bin/python
"""
Translate Japanese comments and docstrings in Python files to English.
Recursively processes all .py files, updates in-place with AST validation.
"""

import ast
import multiprocessing as mp
import re
from pathlib import Path
from typing import Optional, Tuple

from deep_translator import GoogleTranslator

# Initialize translator once per process
translator = None


def get_translator():
    """Get or create translator instance for current process"""
    global translator
    if translator is None:
        translator = GoogleTranslator(source="ja", target="en")
    return translator


def translate_text(text: str) -> str:
    """Translate Japanese text to English, preserving non-Japanese content"""
    if not text or not text.strip():
        return text

    # Skip if no Japanese characters
    if not re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text):
        return text

    try:
        translated = get_translator().translate(text)
        return translated if translated else text
    except Exception as e:
        print(f"Translation error: {e} for text: {text[:50]}")
        return text


class CommentDocstringTranslator(ast.NodeTransformer):
    """AST transformer that translates comments and docstrings"""

    def __init__(self, file_content: str):
        self.file_content = file_content
        self.modified = False

    def translate_docstring(self, node) -> Optional[str]:
        """Translate node docstring if present"""
        docstring = ast.get_docstring(node)
        if docstring and re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", docstring):
            translated = translate_text(docstring)
            if translated != docstring:
                self.modified = True
                return translated
        return None

    def visit_FunctionDef(self, node):
        """Translate function docstrings"""
        new_doc = self.translate_docstring(node)
        if new_doc:
            # Preserve original string type (simple quotes, triple quotes, etc.)
            node.body = [ast.Expr(value=ast.Constant(value=new_doc))] + node.body[1:]
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node):
        """Translate class docstrings"""
        new_doc = self.translate_docstring(node)
        if new_doc:
            node.body = [ast.Expr(value=ast.Constant(value=new_doc))] + node.body[1:]
        self.generic_visit(node)
        return node

    def visit_Module(self, node):
        """Translate module docstring"""
        new_doc = self.translate_docstring(node)
        if new_doc:
            node.body = [ast.Expr(value=ast.Constant(value=new_doc))] + node.body[1:]
        self.generic_visit(node)
        return node


def translate_comments_in_line(line: str) -> Tuple[str, bool]:
    """Translate Japanese comments in a single line"""
    comment_match = re.search(r"#(.*)$", line)
    if not comment_match:
        return line, False

    comment = comment_match.group(1)
    if not re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", comment):
        return line, False

    translated_comment = translate_text(comment)
    if translated_comment != comment:
        new_line = line[: comment_match.start(1)] + translated_comment
        return new_line, True

    return line, False


def translate_file(file_path: Path) -> bool:
    """
    Translate all Japanese comments and docstrings in a Python file.
    Returns True if file was modified.
    """
    try:
        # Read original content
        original_content = file_path.read_text(encoding="utf-8")

        # First, translate comments line by line
        lines = original_content.splitlines(keepends=True)
        modified_lines = []
        comments_modified = False

        for line in lines:
            new_line, modified = translate_comments_in_line(line)
            modified_lines.append(new_line)
            if modified:
                comments_modified = True

        content_with_translated_comments = "".join(modified_lines)

        # Now handle docstrings via AST
        try:
            tree = ast.parse(content_with_translated_comments)
            transformer = CommentDocstringTranslator(content_with_translated_comments)
            new_tree = transformer.visit(tree)
            ast.fix_missing_locations(new_tree)

            # Generate new content from AST
            new_content = ast.unparse(new_tree)
            docstrings_modified = transformer.modified

            # Check if any modifications were made
            if comments_modified or docstrings_modified:
                # Final check: ensure no Japanese characters remain
                if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", new_content):
                    print(f"Warning: Some Japanese characters remain in {file_path}")

                    # Fallback: aggressive translation of any remaining Japanese
                    def aggressive_translate(match):
                        return translate_text(match.group(0))

                    new_content = re.sub(
                        r"[^\w\s\.\,\!\?\;\:\'\"\(\)\[\]\{\}\@\#\$\%\^\&\*\-\+\=\\\/\|\<\>]*(?:[\u3040-\u30ff\u4e00-\u9fff]+[^\w\s\.\,\!\?\;\:\'\"\(\)\[\]\{\}\@\#\$\%\^\&\*\-\+\=\\\/\|\<\>]*)+",
                        aggressive_translate,
                        new_content,
                    )

                # Write back to file
                file_path.write_text(new_content, encoding="utf-8")
                print(f"✓ Updated: {file_path}")
                return True
            else:
                return False

        except SyntaxError as e:
            print(f"✗ Syntax error in {file_path}: {e}. File not modified.")
            return False

    except Exception as e:
        print(f"✗ Error processing {file_path}: {e}")
        return False


def process_file_wrapper(file_path_str: str) -> Tuple[str, bool]:
    """Wrapper for multiprocessing"""
    return file_path_str, translate_file(Path(file_path_str))


def main():
    """Main function to recursively process all Python files"""
    import sys
    from pathlib import Path

    # Get directory from command line or use current directory
    start_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    start_path = Path(start_dir).resolve()

    if not start_path.exists():
        print(f"Error: Path '{start_path}' does not exist")
        sys.exit(1)

    print(f"Scanning for Python files in: {start_path}")

    # Find all Python files recursively
    py_files = list(start_path.rglob("*.py"))
    print(f"Found {len(py_files)} Python files")

    if not py_files:
        print("No Python files found")
        return

    # Process files in parallel
    with mp.Pool(processes=mp.cpu_count()) as pool:
        results = pool.map(process_file_wrapper, [str(f) for f in py_files])

    # Summary
    modified_count = sum(1 for _, modified in results if modified)
    print(f"\n{'=' * 50}")
    print(f"Completed! Modified {modified_count} out of {len(py_files)} files")

    # Double-check for any remaining Japanese text
    print("\nDouble-checking for any remaining Japanese characters...")
    remaining = []
    for file_path in py_files:
        content = file_path.read_text(encoding="utf-8")
        if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", content):
            remaining.append(file_path)

    if remaining:
        print(f"⚠ Warning: Japanese characters found in {len(remaining)} files:")
        for f in remaining[:10]:  # Show first 10
            print(f"  - {f}")
        if len(remaining) > 10:
            print(f"  ... and {len(remaining) - 10} more")
    else:
        print("✓ No Japanese characters found in any file!")


if __name__ == "__main__":
    main()
