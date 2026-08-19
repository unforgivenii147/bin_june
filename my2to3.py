#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import sys
from lib2to3 import refactor
from os import scandir as os_scandir
from pathlib import Path
from dh import mpf3, get_pyfiles


fixers = collect_fixers()


def collect_fixers():
    import pkgutil
    from lib2to3 import fixes

    fixer_names = []
    for _, modname, is_pkg in pkgutil.iter_modules(fixes.__path__, prefix="lib2to3.fixes."):
        if not is_pkg:
            fixer_names.append(modname)
    return fixer_names


def refactor_file(filepath: Path) -> None:
    options = {"print_function": True}
    tool = refactor.RefactoringTool(fixers, options)
    try:
        original = filepath.read_text()
        tree = tool.refactor_string(original, str(filepath))
        new_content = str(tree)
        if original == new_content:
            print(f"  nothing changed: {filepath}")
        else:
            filepath.write_text(new_content)
            print(f"  refactored:      {filepath}")
    except Exception as exc:
        print(f"  ERROR {filepath}: {exc}", file=sys.stderr)


def main() -> None:
    cwd = Path.cwd()
    files = get_pyfiles(cwd)
    mpf3(refactor_file, files)


if __name__ == "__main__":
    main()
