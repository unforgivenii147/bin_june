#!/data/data/com.termux/files/home/.local/bin/python
import argparse
import concurrent.futures
import os
import tokenize
import warnings
from pathlib import Path


def process_file(file_path: Path, auto_fix: bool = False) -> dict:
    """
    Analyzes a single Python file for invalid escape sequences.
    Optionally auto-fixes them by prefixing string literals with 'r'.
    """
    result = {"path": file_path, "has_issues": False, "fixed": False, "errors": [], "warnings": []}

    # Step 1: Detect invalid escape sequences using compile inside a warning catcher
    try:
        content_bytes = file_path.read_bytes()
    except Exception as e:
        result["errors"].append(f"Could not read file: {e}")
        return result

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always", SyntaxWarning)
        try:
            compile(content_bytes, str(file_path), "exec")
        except SyntaxError as se:
            if "invalid escape sequence" in str(se):
                result["has_issues"] = True
                result["errors"].append(f"Line {se.lineno}: SyntaxError: {se.msg}")
            else:
                # Skip files with unrelated syntax errors so we don't break them
                return result

        for w in caught_warnings:
            if issubclass(w.category, SyntaxWarning) and "invalid escape sequence" in str(w.message):
                result["has_issues"] = True
                line_no = getattr(w, "lineno", "Unknown")
                result["warnings"].append(f"Line {line_no}: SyntaxWarning: {w.message}")

    # Step 2: If issues are found and auto_fix is enabled, modify the tokens
    if result["has_issues"] and auto_fix:
        try:
            modified_tokens = []
            is_modified = False

            with file_path.open("rb") as f:
                tokens = list(tokenize.tokenize(f.readline))

            for tok in tokens:
                # Check for string tokens that contain an invalid backslash
                # Skip if it is already a raw string (starts with r/R) or byte string (b/B)
                if tok.type == tokenize.STRING:
                    prefix = ""
                    text = tok.string

                    # Separate existing prefixes (like f, u, etc.)
                    for char in text:
                        if char.lower() in "frub":
                            prefix += char
                        else:
                            break

                    actual_str = text[len(prefix) :]

                    # If it has a backslash and isn't already a raw string literal
                    if "\\" in actual_str and "r" not in prefix.lower():
                        # Test if compiling this individual string token causes a warning
                        with warnings.catch_warnings(record=True) as str_warnings:
                            warnings.simplefilter("always", SyntaxWarning)
                            try:
                                # Wrap in print to make it valid standalone syntax statement
                                compile(f"_{prefix}{actual_str}", "<string>", "exec")
                            except (SyntaxError, SyntaxWarning):
                                pass

                            # If a warning triggered, this specific token is a culprit
                            if any("invalid escape sequence" in str(sw.message) for sw in str_warnings):
                                # Prepend 'r' to the prefix safely
                                new_prefix = "r" + prefix if "r" not in prefix.lower() else prefix
                                tok = tok._replace(string=f"{new_prefix}{actual_str}")
                                is_modified = True

                modified_tokens.append(tok)

            if is_modified:
                # Untokenize converts the updated token stream back into valid source code bytes
                fixed_bytes = tokenize.untokenize(modified_tokens)
                file_path.write_bytes(fixed_bytes)
                result["fixed"] = True

        except Exception as e:
            result["errors"].append(f"Failed to auto-fix: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Find and optionally fix invalid escape sequences in Python files using parallel processing."
    )
    parser.add_argument(
        "directory", type=str, nargs="?", default=".", help="The target directory to scan (default: current directory)."
    )
    parser.add_argument(
        "-a",
        "--auto-fix",
        action="store_true",
        help="Automatically fix invalid escapes by adding an 'r' prefix to offending strings.",
    )

    args = parser.parse_args()
    target_dir = Path(args.directory)

    if not target_dir.is_dir():
        print(f"❌ Error: {target_dir} is not a valid directory.")
        return

    # Find all Python files recursively using pathlib
    py_files = list(target_dir.rglob("*.py"))

    # Exclude the script itself if it's in the target directory
    script_path = Path(__file__).resolve()
    py_files = [f for f in py_files if f.resolve() != script_path]

    print(f"🔍 Found {len(py_files)} Python files. Processing in parallel across {os.cpu_count() or 1} cores...")
    if args.auto_fix:
        print("🛠️  Auto-fix flag (-a) is active. Offending string literals will be converted to raw strings.")
    print("-" * 60)

    total_issues = 0
    total_fixed = 0

    # Process files in parallel using a ProcessPoolExecutor (bypasses Python's GIL for heavy file parsing)
    with concurrent.futures.ProcessPoolExecutor() as executor:
        # Map tasks to workers
        futures = {executor.submit(process_file, f, args.auto_fix): f for f in py_files}

        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            path_rel = res["path"].relative_to(target_dir)

            if res["has_issues"]:
                total_issues += 1
                status = "🔧 FIXED" if res["fixed"] else "⚠️  WARNING"
                print(f"[{status}] {path_rel}")

                # Print individual line details
                for w in res["warnings"]:
                    print(f"   -> {w}")
                for e in res["errors"]:
                    print(f"   -> {e}")

                if res["fixed"]:
                    total_fixed += 1
                print()

    print("=" * 60)
    print(f"📊 Scan Complete.")
    print(f"   Files with issues: {total_issues}")
    if args.auto_fix:
        print(f"   Files successfully fixed: {total_fixed}")


if __name__ == "__main__":
    main()
