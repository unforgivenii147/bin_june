#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import mmap
import re
import tokenize
from collections import deque
from collections.abc import Callable
from mmap import mmap
from pathlib import Path


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "lazy"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


SIZE_THRESHOLD = 1 * 1024 * 1024
OLD_PRINT_RE = re.compile(r"(?m)^[ \t]*print[ \t]+[^(\n]")


def _open_source(filepath: str):
    size = Path(filepath).stat().st_size
    f = Path(filepath).open("rb")
    if size > SIZE_THRESHOLD:
        return mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    return f


def _read_text(filepath: str) -> str | None:
    try:
        with Path(filepath).open(encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None


def _has_rich_print_import(text: str) -> bool:
    return "from rich import print" in text


def _is_in_commented_code(text: str, line_start: int) -> bool:
    """Check if the line is inside a multi-line comment or docstring."""
    lines = text.splitlines(True)  # Keep line endings
    if line_start >= len(lines):
        return False

    # Track if we're inside a multi-line string/comment
    in_multiline = False
    multiline_delimiter = None

    for i, line in enumerate(lines):
        if i == line_start:
            # Check if current line is a comment
            stripped = line.lstrip()
            if stripped.startswith("#"):
                return True
            break
        # Check for multiline strings/docstrings
        for quote in ['"""', "'''"]:
            pos = line.find(quote)
            if pos != -1:
                if in_multiline and multiline_delimiter == quote:
                    # Closing delimiter
                    in_multiline = False
                    multiline_delimiter = None
                elif not in_multiline:
                    # Opening delimiter
                    in_multiline = True
                    multiline_delimiter = quote
                break
    return in_multiline


def regex_flag(filepath: str) -> bool:
    text = _read_text(filepath)
    if not text:
        return False
    if _has_rich_print_import(text):
        return False
    return bool(OLD_PRINT_RE.search(text))


def tokenizer_confirm(filepath: str) -> tuple[str, int] | None:
    """Return (line_content, line_number) if print without parentheses found."""
    try:
        src = _open_source(filepath)
        tokens = list(tokenize.tokenize(src.readline))
    except Exception:
        return None

    # Get the source text for comment/docstring checking
    text = _read_text(filepath)
    if not text:
        return None

    for i, tok in enumerate(tokens):
        if tok.type == tokenize.NAME and tok.string == "print":
            # Check if this is a standalone print or print with parentheses
            line = tok.line.rstrip()
            if line.strip() == "print":
                continue

            # Check if this token is in a comment or docstring
            line_num = tok.start[0]

            # Skip if in comment or docstring
            if _is_in_commented_code(text, line_num - 1):
                continue

            j = i + 1
            while j < len(tokens) and tokens[j].type in {
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
            }:
                j += 1

            # Check if print has parentheses
            if j < len(tokens) and tokens[j].string != "(":
                # Additional check: if this is a comment line, skip it
                if line.lstrip().startswith("#"):
                    continue
                return line, line_num
    return None


def autofix_file(filepath: str) -> bool:
    """Fix Python 2 print statements by adding parentheses."""
    try:
        with Path(filepath).open(encoding="utf-8") as f:
            lines = f.readlines()

        # Skip if rich print is already imported
        if any(l.strip() == "from rich import print" for l in lines):
            return False

        changed = False
        for i, line in enumerate(lines):
            stripped = line.lstrip()

            # Skip comment lines
            if stripped.startswith("#"):
                continue

            # Skip docstring lines
            if '"""' in stripped or "'''" in stripped:
                continue

            # Skip standalone print (no arguments)
            if stripped.rstrip() == "print":
                continue

            # Check for print without parentheses: print "something"
            if stripped.startswith("print ") and not stripped.startswith("print("):
                indent = line[: len(line) - len(stripped)]
                content = stripped[len("print ") :].rstrip()
                lines[i] = f"{indent}print({content})\n"
                changed = True

        if changed:
            with Path(filepath).open("w", encoding="utf-8") as f:
                f.writelines(lines)
        return changed
    except Exception:
        return False


def process_file(filepath: str, autofix: bool = False) -> str | None:
    """Process a single file: detect and optionally fix print statements."""
    if not regex_flag(filepath):
        return None

    confirmed = tokenizer_confirm(filepath)
    if not confirmed:
        return None

    line, line_num = confirmed

    if autofix:
        if autofix_file(filepath):
            return f"{filepath} (fixed)\n  Line {line_num}: {line}"
        else:
            return f"{filepath} (could not fix)\n  Line {line_num}: {line}"
    else:
        return f"{filepath}\n  Line {line_num}: {line}"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Detect and fix Python 2 print statements")
    parser.add_argument("path", nargs="?", default=".", help="Path to file or directory to scan")
    parser.add_argument("-a", "--autofix", action="store_true", help="Automatically fix print statements")
    args = parser.parse_args()

    # Get Python files
    path = Path(args.path)
    if path.is_file() and path.suffix == ".py":
        files = [path]
    else:
        files = get_files(path, ext=[".py"])

    if not files:
        print("No Python files found.")
        return

    # Process files in parallel
    results = mpf3(process_file, files, autofix=args.autofix)

    # Display results
    found_issues = False
    for result in results:
        if result:
            print(result)
            found_issues = True

    if not found_issues:
        print("No Python 2 print statements found.")
    else:
        if args.autofix:
            print("\n✓ Files with issues have been automatically fixed.")
        else:
            print("\nRun with --autofix to automatically fix these issues.")


if __name__ == "__main__":
    main()
