#!/data/data/com.termux/files/usr/bin/env python


import ast
import re
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from dh import DOC_TH1, DOC_TH2, get_pyfiles

COMMENT_AND_DOCSTRING_REGEX = re.compile(
    f"(?:^(\\s*)#.*$)|(?:^(\\s*)({DOC_TH2}).*?(\\3)|^(\\s*)({DOC_TH1}).*?(\\5))|(?:\\b(def|class)\\s+\\w+[^():]*\\([^)]*\\)\\s*:\\s*)(\\s*)((DOC_TH2).*?(\\7)|({DOC_TH1}).*?(\\9))",
    re.MULTILINE | re.DOTALL,
)
DOCSTRING_START_REGEX = re.compile(f"^\\s*({DOC_TH2}|{DOC_TH1}).*?(\\1)\\s*", re.MULTILINE | re.DOTALL)
MAX_WORKERS = 4


def strip_comments_and_docstrings(file_path_str) -> bool:
    file_path = Path(file_path_str)
    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    original_content = ""
    try:
        original_content = Path(file_path).read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return False
    cleaned_content = DOCSTRING_START_REGEX.sub("\x01", original_content, count=3)

    def replace_comments(match):
        _indent1, comment1, quote1, _indent2, _quote2, fn_type, indent3, quote3, quote4 = match.groups()
        if comment1:
            return ""
        if quote1:
            return match.group(0)
        if quote3 or quote4:
            return f"{fn_type}{indent3}"
        return match.group(0)

    no_single_line_comments = re.sub("^\\s*#.*$", "", original_content, flags=re.MULTILINE)
    try:
        tree = ast.parse(no_single_line_comments)
        cleaned_content_heuristic = DOCSTRING_START_REGEX.sub("\x01", no_single_line_comments, count=3)
        try:
            ast.parse(cleaned_content_heuristic)
            final_code = cleaned_content_heuristic
        except SyntaxError:
            print(f"Syntax error after stripping comments/docstrings from {file_path}. Reverting.")
            return False
    except SyntaxError as e:
        print(f"Original code has syntax error: {file_path} - {e}. Skipping.")
        return False
    try:
        shutil.copy2(file_path, backup_path)
        print(f"Backup created: {backup_path}")
    except Exception as e:
        print(f"Error creating backup for {file_path}: {e}")
        return False
    try:
        Path(file_path).write_text(final_code, encoding="utf-8")
        print(f"Successfully stripped comments/docstrings from {file_path}")
        return True
    except Exception as e:
        print(f"Error writing cleaned file {file_path}: {e}")
        try:
            shutil.move(backup_path, file_path)
            print(f"Restored original content from backup for {file_path}")
        except Exception as restore_e:
            print(f"CRITICAL ERROR: Failed to write cleaned file and restore backup for {file_path}: {restore_e}")
        return False


def process_directory(directory: str) -> None:
    python_files = get_pyfiles(directory)
    print(f"Found {len(python_files)} Python files to process.")
    processed_count = 0
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(strip_comments_and_docstrings, file_path): file_path for file_path in python_files}
        for future in futures:
            file_path = futures[future]
            try:
                success = future.result()
                if success:
                    processed_count += 1
            except Exception as e:
                print(f"Error processing future for {file_path}: {e}")
    print(f"""
Finished processing. Successfully stripped comments/docstrings from {processed_count}/{len(python_files)} files.""")


if __name__ == "__main__":
    target_directory = "."
    print(f"Starting comment and docstring stripping in directory: {Path(target_directory).resolve()}")
    process_directory(target_directory)
