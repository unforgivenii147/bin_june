#!/data/data/com.termux/files/usr/bin/env python


import shutil
import sys
from pathlib import Path

EMPTY_MODE = "-e" in sys.argv
REMOVE_MODE = "-r" in sys.argv
SKIP_DIRS = {"lazy", ".git", "var"}
JUNK_FILES = {"license.md", "license.txt"}
REMOVABLE_EXTENSIONS = {".txt", ".md"}
JUNK_EXTENSIONS = {".tmp", ".bak", ".log", ".pyc"}


def empty_it(path: Path) -> None:
    try:
        path.write_text("", encoding="utf-8")
    except OSError as e:
        print(f"Error emptying {path}: {e}", file=sys.stderr)


def remove_it(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as e:
        print(f"Error removing {path}: {e}", file=sys.stderr)


def should_skip(path: Path) -> bool:
    return any((skip_dir in path.parts for skip_dir in SKIP_DIRS))


def has_multiple_suffixes(path: Path) -> bool:
    return len(path.suffixes) > 1


def main() -> None:
    cwd = Path.cwd()
    removed_count = 0
    for path in cwd.rglob("*"):
        if should_skip(path):
            continue
        loname = path.name.lower()
        if path.is_file() and loname in {
            ".pyformat_cache.json",
            "simz.json",
            "changelog.md",
            "changelog.txt",
            "license.rst",
            "license.md",
            "license.txt",
            "license.mit",
            "authors.md",
            "changelog",
            "license",
            "author",
            "authors",
            "copying",
            ".gitkeep",
            ".dirinfo",
            "copyright",
            "contributing",
            ".travis.yml",
            "third_party_notices",
        }:
            remove_it(path)
            print(f"{path.relative_to(cwd)} removed")
            continue
        rel_path = path.relative_to(cwd)
        if loname in JUNK_FILES:
            suffix = path.suffix.lower()
            if suffix in REMOVABLE_EXTENSIONS and (not has_multiple_suffixes(path)):
                remove_it(path)
                print(f"{rel_path} removed.")
                removed_count += 1
            elif suffix in REMOVABLE_EXTENSIONS:
                print(f"{rel_path} skipped (multiple suffixes detected).")
            continue
        if path.is_file() and any((loname.endswith(ext) for ext in JUNK_EXTENSIONS)):
            remove_it(path)
            print(rel_path)
            removed_count += 1
            continue
        if path.is_dir() and loname == "licenses" and ("dist-info" in path.parent.name):
            remove_it(path)
            print(rel_path)
            removed_count += 1
            continue
        if any((junk in loname for junk in JUNK_FILES)):
            suffix = path.suffix.lower()
            if suffix not in REMOVABLE_EXTENSIONS:
                continue
            if has_multiple_suffixes(path):
                print(f"{rel_path} skipped (multiple suffixes detected).")
                continue
            if REMOVE_MODE:
                remove_it(path)
            else:
                empty_it(path)
            print(rel_path)
            removed_count += 1
    if removed_count:
        print(f"\n{removed_count} item(s) removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
