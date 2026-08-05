#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Assuming 'dh' is a local module in the same directory
from dh import MIME2EXT, SHEBANG_MAP, colored, cprint, is_binary, runcmd, unique_path

SKIP_DIRS = {".git", "__pycache__"}
SKIP_EXTS = {".css", ".js"}


def fix_by_shebang(path: Path) -> str | None:
    """Determine file extension by reading the shebang."""
    if is_binary(path):
        return None
    try:
        with path.open("rb") as f:
            first_line = f.readline(256)
        if not first_line.startswith(b"#!"):
            return None
        shebang = first_line.decode("utf-8", errors="replace").strip()
        for interpreter, ext in SHEBANG_MAP.items():
            if interpreter in shebang:
                return ext
    except Exception:
        return None
    return None


def get_file_mime(path: Path) -> str | None:
    """Fetch the MIME type of a file using the `file` command."""
    result = runcmd(["file", "--brief", "--mime-type", str(path)])
    if result["exit_code"] != 0:
        return None
    mime = result["stdout"].strip()
    return mime or None


def safe_rename(old: Path, new: Path) -> Path | None:
    """Safely rename a file, resolving name collisions. Returns the new path or None."""
    try:
        # unique_path should handle adding a suffix like _1, _2 if the file exists
        actual_new_path = unique_path(new)
        old.rename(actual_new_path)
        return actual_new_path
    except Exception:
        return None


def process_directory(directory: Path) -> list[dict]:
    """Scan directory and return files with mismatched extensions."""
    mismatches: list[dict] = []

    # Path.walk() is available natively in Python 3.12
    for root, dirs, files in directory.walk():
        # Filter out skipped directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for file in files:
            file_path = root / file

            if not file_path.is_file() or file_path.is_symlink():
                continue
            if file_path.stat().st_size == 0:
                continue

            current_ext = file_path.suffix.lower()
            if current_ext in SKIP_EXTS:
                continue

            mime = None
            expected_ext = None

            # 1. Check by shebang
            shebang_ext = fix_by_shebang(file_path)
            if shebang_ext and current_ext != shebang_ext:
                mime = "shebang"
                expected_ext = shebang_ext

            # 2. Check by MIME type if shebang didn't find a mismatch
            if not expected_ext:
                mime = get_file_mime(file_path)
                if not mime or mime == "text/plain":
                    continue

                expected_exts = MIME2EXT.get(mime, [])
                if not expected_exts:
                    continue

                expected_ext = expected_exts[0]
                if current_ext == expected_ext or current_ext in expected_exts:
                    continue

            # Mismatch found
            # Construct new path without the old extension first, then add the expected
            new_name = file_path.name[: -len(file_path.suffix)] if file_path.suffix else file_path.name
            new_name = f"{new_name}{expected_ext}"
            new_path = file_path.with_name(new_name)

            mismatches.append(
                {
                    "path": file_path,
                    "mime": mime,
                    "current_ext": current_ext or "(none)",
                    "expected_ext": expected_ext,
                    "new_path": new_path,
                }
            )

    return mismatches


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix file extension mismatches by analyzing file content.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("-n", "--no-dry-run", action="store_true", help="Apply changes (default is dry-run preview)")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip per-file confirmation when applying changes")
    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        cprint(f"Error: {directory} is not a valid directory", color="red", attrs=["bold"])
        sys.exit(1)

    mismatches = process_directory(directory)

    if not mismatches:
        cprint("No mismatches found.", color="green", attrs=["bold"])
        sys.exit(0)

    cprint(f"\nFound {len(mismatches)} mismatched file(s):\n", color="yellow", attrs=["bold"])

    for item in mismatches:
        orig = colored(str(item["path"]), color="red", attrs=["bold"])
        mime_info = colored(f"mime={item['mime']}", color="cyan")
        expected = colored(f"expected ext={item['expected_ext']}", color="green")
        proposed_name = colored(item["new_path"].name, color="green", attrs=["bold"])

        print(orig)
        print(f"  {mime_info} | {expected}")
        print(f"  Proposed: {proposed_name}")

        if args.no_dry_run:
            # Confirm unless -y was passed
            if not args.yes:
                response = input(f"  Rename {item['path'].name} -> {item['new_path'].name}? [y/N] ").strip().lower()
                if response != "y":
                    print("  Skipped.\n")
                    continue

            actual_new_path = safe_rename(item["path"], item["new_path"])
            if actual_new_path:
                # Check if it had to be renamed differently due to path conflicts
                if actual_new_path != item["new_path"]:
                    cprint(f"  Renamed to {actual_new_path.name} (name adjusted to avoid conflict)", color="yellow")
                else:
                    cprint(f"  Renamed to {actual_new_path.name}", color="green")
            else:
                cprint("  Failed to rename", color="red", attrs=["bold"])
        print()

    if not args.no_dry_run:
        cprint("Dry run complete. Pass '-n' to apply changes.", color="yellow", attrs=["bold"])
    else:
        cprint("Done.", color="green", attrs=["bold"])


if __name__ == "__main__":
    main()
