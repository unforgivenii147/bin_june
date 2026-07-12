#!/data/data/com.termux/files/usr/bin/env python

"""
Scan ~/bin for Python scripts that import from the custom 'dh' package.
Count how many times each function from 'dh' is imported and used,
then save a report to ~/dh_usage.txt.
"""

import ast
import sys
from collections import Counter
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


# ── config ────────────────────────────────────────────────────────────────────

BIN_DIR = Path.home() / "bin"
REPORT = Path.home() / "dh_usage.txt"
PACKAGE = "dh"  # your custom package name

# ── helpers ───────────────────────────────────────────────────────────────────


def extract_dh_imports(filepath: Path) -> list[str]:
    """
    Parse a Python file and return a list of function names imported
    from the 'dh' package (e.g. 'from dh import get_files' → ['get_files']).
    Also catches 'from dh.submodule import foo' and 'import dh; dh.bar()'.
    """
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"   ⚠️  Skipping {filepath.name}: {e}")
        return []

    imported: list[str] = []

    for node in ast.walk(tree):
        # from dh import foo, bar
        if isinstance(node, ast.ImportFrom):
            if node.module and (node.module == PACKAGE or node.module.startswith(PACKAGE + ".")):
                for alias in node.names:
                    imported.append(alias.name if alias.asname is None else alias.asname)

        # import dh  →  then look for dh.something() calls
        # We handle this separately below.

    # For 'import dh' style, find attribute accesses: dh.get_files()
    # We need to know which names refer to the dh module.
    dh_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == PACKAGE or alias.name.startswith(PACKAGE + "."):
                    name = alias.asname if alias.asname else alias.name
                    dh_names.add(name)

    # Now find calls like dh.get_files() or dh.submodule.func()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # dh.get_files(...)
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id in dh_names:
                    imported.append(func.attr)
            # dh.submodule.get_files(...)
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
                # walk up to find the root name
                root = func.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name) and root.id in dh_names:
                    imported.append(func.attr)

    return imported


def count_calls(filepath: Path, func_names: list[str]) -> dict[str, int]:
    """
    For a given file and list of imported function names,
    count how many times each function is actually *called* in the file.
    """
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return {}

    name_set = set(func_names)
    counter: dict[str, int] = {name: 0 for name in func_names}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # direct call: get_files(...)
            if isinstance(func, ast.Name) and func.id in name_set:
                counter[func.id] += 1
            # attribute call: dh.get_files(...) — already counted in extract,
            # but we also count bare calls if imported via 'from dh import get_files'
            # The 'from' style makes the function a local name, so ast.Name catches it.

    return counter


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    if not BIN_DIR.is_dir():
        print(f"❌ {BIN_DIR} does not exist or is not a directory.")
        sys.exit(1)

    py_files = sorted(BIN_DIR.glob("*.py"))
    if not py_files:
        print(f"⚠️  No .py files found in {BIN_DIR}.")
        return

    print(f"🔍 Scanning {len(py_files)} Python file(s) in {BIN_DIR} ...\n")

    # Collect all imports and call counts per file
    all_imports: dict[str, Counter] = {}  # func_name → total call count
    per_file: list[tuple[str, dict[str, int]]] = []

    for f in py_files:
        funcs = extract_dh_imports(f)
        if not funcs:
            continue

        calls = count_calls(f, funcs)
        per_file.append((f.name, calls))

        for name, count in calls.items():
            if name not in all_imports:
                all_imports[name] = Counter()
            all_imports[name][f.name] = count

    if not all_imports:
        print(f"✅ No imports from '{PACKAGE}' found in any script.")
        REPORT.write_text(f"No imports from '{PACKAGE}' found in {BIN_DIR}.\n")
        return

    # ── build report ──────────────────────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"{'=' * 70}")
    lines.append(f"  dh Usage Report — generated {__import__('datetime').datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"{'=' * 70}")
    lines.append(f"  Scanned: {BIN_DIR}")
    lines.append(f"  Files with dh imports: {len(per_file)}")
    lines.append(f"  Unique dh functions used: {len(all_imports)}")
    lines.append("")

    # Summary table: function → total calls
    lines.append(f"{'Function':<30} {'Total Calls':<15} {'Files Used In':<15}")
    lines.append("-" * 70)
    for func_name in sorted(all_imports, key=lambda n: -sum(all_imports[n].values())):
        total = sum(all_imports[func_name].values())
        files_used = len(all_imports[func_name])
        lines.append(f"{func_name:<30} {total:<15} {files_used:<15}")
    lines.append("")

    # Per-file breakdown
    lines.append(f"{'─' * 70}")
    lines.append("  PER-FILE BREAKDOWN")
    lines.append(f"{'─' * 70}")
    for fname, calls in sorted(per_file, key=lambda x: -sum(x[1].values())):
        total = sum(calls.values())
        lines.append(f"\n  📄 {fname}  ({total} call(s))")
        for func_name in sorted(calls, key=lambda n: -calls[n]):
            if calls[func_name] > 0:
                lines.append(f"      {func_name:<30} {calls[func_name]} time(s)")

    lines.append("")
    lines.append(f"{'=' * 70}")
    lines.append("  END OF REPORT")
    lines.append(f"{'=' * 70}")

    report_text = "\n".join(lines)
    REPORT.write_text(report_text, encoding="utf-8")

    print(report_text)
    print(f"\n✅ Report saved to {REPORT}")


if __name__ == "__main__":
    main()
