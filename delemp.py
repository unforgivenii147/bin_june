#!/data/data/com.termux/files/usr/bin/env python
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from dh import get_nobinary

# ANSI escape codes for coloring terminal text
CYAN = "\033[36m"
RESET = "\033[0m"


def process_file(path: Path, max_blank_keep: int) -> tuple[Path, int]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return (path, 0)

    lines = text.splitlines()
    new_lines = []
    blank_run = 0
    removed = 0

    for line in lines:
        if not line.strip():
            blank_run += 1
            if blank_run <= max_blank_keep:
                new_lines.append("")
            else:
                removed += 1
        else:
            blank_run = 0
            new_lines.append(line)

    if removed > 0:
        output_text = "\n".join(new_lines) + ("\n" if new_lines else "")
        path.write_text(output_text, encoding="utf-8")

    return (path, removed)


def print_result(path: Path, cwd: Path, removed: int):
    # Try to get the path relative to the current directory
    try:
        rel_path = path.relative_to(cwd)
    except ValueError:
        rel_path = path  # Fallback to absolute if it's outside the cwd

    # Format the number in cyan
    print(f"{rel_path}  {CYAN}{removed}{RESET}")


def main():
    parser = argparse.ArgumentParser(description="Remove blank lines from files recursively.")
    parser.add_argument("-n", type=int, default=1, help="Max number of consecutive blank lines to keep (default: 1).")
    parser.add_argument("targets", nargs="*", help="Files or directories to process (defaults to current directory).")
    args = parser.parse_args()

    cwd = Path.cwd()
    files = []
    if args.targets:
        for target in args.targets:
            p = Path(target)
            if p.is_file():
                files.append(p.resolve())  # Use resolve to ensure path math works smoothly
            elif p.is_dir():
                files.extend(f.resolve() for f in get_nobinary(p))
    else:
        files = [f.resolve() for f in get_nobinary(cwd)]

    if not files:
        print("No files found to process.")
        sys.exit(0)

    if len(files) == 1:
        path, removed = process_file(files[0], args.n)
        print_result(path, cwd, removed)
        sys.exit(0)

    total_removed = 0
    with ThreadPoolExecutor() as exe:
        futures = {exe.submit(process_file, f, args.n): f for f in files}
        for fut in as_completed(futures):
            path, removed = fut.result()
            total_removed += removed
            print_result(path, cwd, removed)

    print(f"\nTotal blank lines removed: {CYAN}{total_removed}{RESET}")


if __name__ == "__main__":
    main()
