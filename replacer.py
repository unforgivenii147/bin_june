#!/data/data/com.termux/files/usr/bin/env python
import argparse
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def is_binary(path: (Path | str)) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def process_file(path: Path, search_text, replace_text=None, dry_run=False) -> bool:
    path = Path(path)
    try:
        content = path.read_text(encoding="utf-8")
        replacement = replace_text if replace_text is not None else ""
        escaped_search = re.escape(search_text)
        pattern = re.compile(escaped_search)
        if pattern.search(content):
            if dry_run:
                matches = list(pattern.finditer(content))
                print(f"[DRY RUN] Found {len(matches)} match(es) in {path}")
                for i, match in enumerate(matches[:3]):
                    start = max(0, match.start() - 20)
                    end = min(len(content), match.end() + 20)
                    context = content[start:end]
                    context = context.replace("\n", " ").strip()
                    print(f"  Match {i + 1}: ...{context}...")
                if len(matches) > 3:
                    print(f"  ... and {len(matches) - 3} more matches")
            else:
                new_content = pattern.sub(replacement, content)
                Path(path).write_text(new_content, encoding="utf-8")
                print(f"Updated: {path}")
            return True
        return False
    except (UnicodeDecodeError, PermissionError, IsADirectoryError):
        return False
    except Exception as e:
        print(f"Error processing {path}: {e}", file=sys.stderr)
        return False


def replace_in_files(search_text, replace_text=None, target_file=None, dry_run=False) -> tuple[int, int]:
    exclude_dirs = {".git", "build", "dist", "__pycache__", "node_modules"}
    files_processed = 0
    files_changed = 0
    if target_file:
        if Path(target_file).is_file() and not Path(target_file).is_symlink():
            print(f"Processing file: {target_file}")
            if process_file(target_file, search_text, replace_text, dry_run):
                files_changed += 1
            files_processed += 1
        else:
            print(f"Error: {target_file} is not a valid file", file=sys.stderr)
        return files_processed, files_changed
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for filename in files:
            path = Path(root) / filename
            if path.is_symlink() or is_binary(path):
                continue
            files_processed += 1
            if process_file(path, search_text, replace_text, dry_run):
                files_changed += 1
            if files_processed % 100 == 0:
                print(f"Processed {files_processed} files...", end="\r")
    return files_processed, files_changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recursively replace or remove text in files.")
    parser.add_argument(
        "strings",
        nargs="+",
        help="Search text and optional replacement text. If only one string is provided, it will be removed.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying them")
    parser.add_argument("-f", "--file", help="Process only the specified file instead of recursive directory search")
    args = parser.parse_args()
    if len(args.strings) == 2:
        search_text, replace_text = args.strings
        action = f"REPLACING '{search_text}' WITH '{replace_text}'"
    elif len(args.strings) == 1:
        search_text = args.strings[0]
        replace_text = None
        action = f"REMOVING '{search_text}'"
    else:
        parser.error("Please provide either one string (to remove) or two strings (search and replace)")
    if search_text.startswith(("'", '"')) and search_text.endswith(("'", '"')):
        search_text = search_text[1:-1]
    if args.dry_run:
        print("--- RUNNING IN DRY RUN MODE (No files will be modified) ---")
    print(f"--- {action} ---")
    files_processed, files_changed = replace_in_files(
        search_text, replace_text, target_file=args.file, dry_run=args.dry_run
    )
    print(f"\n--- Complete: Processed {files_processed} files, modified {files_changed} files ---")
