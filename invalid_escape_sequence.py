#!/data/data/com.termux/files/home/.local/bin/python
import argparse
import concurrent.futures
import os
import tokenize
import warnings
from pathlib import Path


def check_and_fix_file(file_path: Path, auto_fix: bool) -> dict:
    """Analyzes a single file for invalid escapes and optionally fixes them."""
    result = {"path": file_path, "has_issues": False, "fixed": False, "messages": []}

    try:
        content_bytes = file_path.read_bytes()
    except Exception as e:
        result["messages"].append(f"Error reading file: {e}")
        return result

    # Step 1: Detect invalid escape sequences using compiler warnings
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always", SyntaxWarning)
        try:
            compile(content_bytes, str(file_path), "exec")
        except SyntaxError as se:
            if "invalid escape sequence" in str(se):
                result["has_issues"] = True
                result["messages"].append(f"Line {se.lineno}: SyntaxError: {se.msg}")
            else:
                return result  # Skip files with unrelated compilation syntax errors

        for w in caught_warnings:
            if issubclass(w.category, SyntaxWarning) and "invalid escape sequence" in str(w.message):
                result["has_issues"] = True
                line_no = getattr(w, "lineno", "Unknown")
                result["messages"].append(f"Line {line_no}: SyntaxWarning: {w.message}")

    # Step 2: Auto-fix tokens if requested and issues exist
    if result["has_issues"] and auto_fix:
        try:
            modified_tokens = []
            is_modified = False

            with file_path.open("rb") as f:
                tokens = list(tokenize.tokenize(f.readline))

            for tok in tokens:
                if tok.type == tokenize.STRING:
                    text = tok.string
                    prefix = ""

                    # Separate existing string modifiers (e.g., f"", b"", u"")
                    for char in text:
                        if char.lower() in "frub":
                            prefix += char
                        else:
                            break

                    actual_str = text[len(prefix) :]

                    # If it contains a backslash and isn't already a raw string literal
                    if "\\" in actual_str and "r" not in prefix.lower():
                        # Test if compiling this individual token triggers an escape warning
                        with warnings.catch_warnings(record=True) as token_warnings:
                            warnings.simplefilter("always", SyntaxWarning)
                            try:
                                compile(f"_{prefix}{actual_str}", "<string>", "exec")
                            except (SyntaxError, SyntaxWarning):
                                pass

                            if any("invalid escape sequence" in str(tw.message) for tw in token_warnings):
                                # Prepend 'r' to convert it safely to a raw string
                                new_prefix = "r" + prefix
                                tok = tok._replace(string=f"{new_prefix}{actual_str}")
                                is_modified = True

                modified_tokens.append(tok)

            if is_modified:
                # Reconstruct files from tokens to completely preserve indentation and layouts
                fixed_bytes = tokenize.untokenize(modified_tokens)
                file_path.write_bytes(fixed_bytes)
                result["fixed"] = True

        except Exception as e:
            result["messages"].append(f"Error while fixing: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Recursively scan and fix Python files for invalid escape sequences.")
    parser.add_argument(
        "-a",
        "--auto-fix",
        action="store_true",
        help="Automatically fix issues by converting offending string literals to raw strings.",
    )
    args = parser.parse_args()

    current_dir = Path(".")
    py_files = list(current_dir.rglob("*.py"))

    # Ignore this runner script itself if it sits in the target directory
    script_path = Path(__file__).resolve()
    py_files = [f for f in py_files if f.resolve() != script_path]

    cpu_cores = os.cpu_count() or 1
    print(f"🔍 Found {len(py_files)} Python files.")
    print(f"⚡ Processing using {cpu_cores} parallel workers...")
    if args.auto_fix:
        print("🛠️  Auto-fix mode is enabled (-a).")
    print("-" * 60)

    issues_count = 0
    fixed_count = 0

    # Process files concurrently using processes to bypass the GIL
    with concurrent.futures.ProcessPoolExecutor(max_workers=cpu_cores) as executor:
        futures = {executor.submit(check_and_fix_file, f, args.auto_fix): f for f in py_files}

        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res["has_issues"]:
                issues_count += 1
                status = "[🔧 FIXED]" if res["fixed"] else "[⚠️  ISSUE]"
                print(f"{status} {res['path']}")

                for msg in res["messages"]:
                    print(f"   -> {msg}")

                if res["fixed"]:
                    fixed_count += 1
                print()

    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   Files with invalid escape sequences: {issues_count}")
    if args.auto_fix:
        print(f"   Files successfully auto-fixed:     {fixed_count}")


if __name__ == "__main__":
    main()
