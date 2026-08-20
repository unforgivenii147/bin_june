#!/data/data/com.termux/files/home/.local/bin/python
import os
import argparse
import re
from pathlib import Path

# Regex patterns for detection
PATTERNS = {
    "import_stmt": re.compile(
        r"^(import pkg_resources|from pkg_resources import .*)", re.MULTILINE
    ),
    "get_dist": re.compile(r"pkg_resources\.get_distribution\((.*?)\)\.version"),
    "parse_version": re.compile(r"pkg_resources\.parse_version\("),
    "resource_filename": re.compile(r"pkg_resources\.resource_filename\("),
    "requirement": re.compile(r"pkg_resources\.Requirement\.parse\("),
}


def fix_content(content):
    """
    Performs basic transformations for common pkg_resources patterns.
    Note: Complex logic might still require manual review.
    """
    new_content = content

    # 1. Replace get_distribution(pkg).version with importlib.metadata.version(pkg)
    if "pkg_resources.get_distribution" in new_content:
        new_content = PATTERNS["get_dist"].sub(
            r"importlib.metadata.version(\1)", new_content
        )
        if "import importlib.metadata" not in new_content:
            new_content = "import importlib.metadata\n" + new_content

    # 2. Replace parse_version with packaging.version.parse
    if "pkg_resources.parse_version" in new_content:
        new_content = PATTERNS["parse_version"].sub(
            "packaging.version.parse(", new_content
        )
        if "from packaging import version" not in new_content:
            new_content = "from packaging import version\n" + new_content

    # 3. Clean up the main import
    new_content = re.sub(
        r"^import pkg_resources\n?", "", new_content, flags=re.MULTILINE
    )

    return new_content


def process_files(autofix=False):
    count_found = 0
    python_files = list(Path(".").rglob("*.py"))

    for file_path in python_files:
        # Skip this script itself
        if file_path.name == os.path.basename(__file__):
            continue

        try:
            #            print(f'processing {file_path}')

            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Could not read {file_path}: {e}")
            continue

        matches = [name for name, regex in PATTERNS.items() if regex.search(content)]

        if matches:
            count_found += 1
            print(f"[{'FIXING' if autofix else 'FOUND'}] {file_path}")
            for m in matches:
                print(f"  - Detected: {m}")

            if autofix:
                fixed_code = fix_content(content)
                file_path.write_text(fixed_code, encoding="utf-8")
                print(f"  - Applied basic fixes to {file_path}")

    print(f"\nSummary: Found {count_found} files containing pkg_resources usage.")
    if not autofix and count_found > 0:
        print("Run with -a to attempt automatic replacement.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect and fix pkg_resources usage.")
    parser.add_argument(
        "-a",
        "--autofix",
        action="store_true",
        help="Attempt to automatically replace simple patterns.",
    )
    args = parser.parse_args()

    process_files(autofix=args.autofix)
