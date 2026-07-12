#!/data/data/com.termux/files/usr/bin/env python

"""
Scan ~/bin for Python scripts and count imports from:
  - Standard library modules
  - Third-party packages (installed via pip)
  - Custom 'dh' package

Save a comprehensive report to ~/dh_usage.txt
"""

import ast
import importlib
import pkgutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


# ── config ────────────────────────────────────────────────────────────────────

BIN_DIR = Path.home() / "bin"
REPORT = Path.home() / "dh_usage.txt"
PACKAGE = "dh"  # your custom package name

# ── stdlib detection ──────────────────────────────────────────────────────────


def get_stdlib_modules() -> set[str]:
    """Return a set of all standard library module names."""
    stdlib = set()
    for module_info in pkgutil.iter_modules():
        name = module_info.name
        if name.startswith("_"):
            continue
        stdlib.add(name)
    # Add common top-level modules that pkgutil might miss
    extra = {
        "os",
        "sys",
        "re",
        "json",
        "math",
        "time",
        "datetime",
        "pathlib",
        "collections",
        "itertools",
        "functools",
        "typing",
        "argparse",
        "logging",
        "subprocess",
        "shutil",
        "tempfile",
        "hashlib",
        "base64",
        "uuid",
        "csv",
        "io",
        "textwrap",
        "string",
        "random",
        "statistics",
        "decimal",
        "fractions",
        "enum",
        "dataclasses",
        "abc",
        "copy",
        "pprint",
        "traceback",
        "warnings",
        "contextlib",
        "threading",
        "multiprocessing",
        "socket",
        "http",
        "urllib",
        "email",
        "xml",
        "html",
        "configparser",
        "ast",
        "inspect",
        "dis",
        "tokenize",
        "compileall",
        "zipfile",
        "tarfile",
        "gzip",
        "bz2",
        "lzma",
        "pickle",
        "shelve",
        "dbm",
        "sqlite3",
        "unittest",
        "doctest",
        "pdb",
        "profile",
        "cProfile",
        "webbrowser",
        "tkinter",
        "turtle",
    }
    stdlib.update(extra)
    return stdlib


def is_stdlib(module_name: str, stdlib_set: set[str]) -> bool:
    """Check if a module (or its top-level parent) is in stdlib."""
    top_level = module_name.split(".")[0]
    return top_level in stdlib_set


def is_third_party(module_name: str, stdlib_set: set[str]) -> bool:
    """Check if a module is third-party (not stdlib, not builtin, not dh)."""
    top_level = module_name.split(".")[0]
    if top_level == PACKAGE:
        return False
    if top_level in stdlib_set:
        return False
    # Built-in modules like __future__
    if top_level.startswith("__"):
        return False
    return True


# ── AST parsing ───────────────────────────────────────────────────────────────


def extract_imports(filepath: Path) -> dict[str, list[str]]:
    """
    Parse a Python file and return:
      {module_name: [list of imported names]}

    Handles:
      - import os
      - import os.path
      - from os import path, getcwd
      - from os.path import join
      - import dh; dh.get_files()  →  module: dh, names: [get_files]
    """
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"   ⚠️  Skipping {filepath.name}: {e}")
        return {}

    imports: dict[str, list[str]] = defaultdict(list)

    for node in ast.walk(tree):
        # import foo, bar
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name
                asname = alias.asname
                # We record the module itself as imported
                if mod not in imports:
                    imports[mod] = []
                # If aliased, record the alias too
                if asname:
                    imports[mod].append(asname)

        # from foo import bar, baz
        if isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module
                for alias in node.names:
                    name = alias.name if alias.asname is None else alias.asname
                    imports[mod].append(name)

    # For 'import dh' style, find attribute accesses: dh.get_files()
    dh_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == PACKAGE or alias.name.startswith(PACKAGE + "."):
                    name = alias.asname if alias.asname else alias.name
                    dh_names.add(name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # dh.get_files(...)
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id in dh_names:
                    imports[PACKAGE].append(func.attr)
            # dh.submodule.get_files(...)
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
                root = func.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name) and root.id in dh_names:
                    imports[PACKAGE].append(func.attr)

    return dict(imports)


def count_calls(filepath: Path, imports: dict[str, list[str]]) -> dict[str, dict[str, int]]:
    """
    For each module, count how many times each imported name is actually called.
    Returns {module: {name: count}}
    """
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return {}

    # Build a reverse mapping: local_name → (module, original_name)
    local_to_import: dict[str, tuple[str, str]] = {}
    for mod, names in imports.items():
        for name in names:
            local_to_import[name] = (mod, name)

    call_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # Direct call: get_files(...)
            if isinstance(func, ast.Name) and func.id in local_to_import:
                mod, name = local_to_import[func.id]
                call_counts[mod][name] += 1
            # Attribute call: os.path.join(...)
            if isinstance(func, ast.Attribute):
                # Check if the object is an imported module
                if isinstance(func.value, ast.Name):
                    obj_name = func.value.id
                    # Check if obj_name is a module we imported
                    for mod, names in imports.items():
                        if mod == obj_name or mod.endswith("." + obj_name):
                            call_counts[mod][func.attr] += 1

    return dict(call_counts)


# ── report generation ─────────────────────────────────────────────────────────


def generate_report(
    per_file_data: list[tuple[str, dict[str, dict[str, int]]]],
    stdlib_set: set[str],
) -> str:
    """Build the full report text."""
    lines: list[str] = []
    now = __import__("datetime").datetime.now()

    # Aggregate stats
    stdlib_counts: Counter = Counter()  # module → total calls
    thirdparty_counts: Counter = Counter()
    dh_counts: Counter = Counter()

    stdlib_files: dict[str, set[str]] = defaultdict(set)
    thirdparty_files: dict[str, set[str]] = defaultdict(set)
    dh_files: dict[str, set[str]] = defaultdict(set)

    for fname, module_calls in per_file_data:
        for mod, func_calls in module_calls.items():
            total = sum(func_calls.values())
            top_level = mod.split(".")[0]

            if top_level == PACKAGE:
                dh_counts[mod] += total
                for func in func_calls:
                    dh_files[func].add(fname)
            elif is_stdlib(mod, stdlib_set):
                stdlib_counts[mod] += total
                for func in func_calls:
                    stdlib_files[func].add(fname)
            else:
                thirdparty_counts[mod] += total
                for func in func_calls:
                    thirdparty_files[func].add(fname)

    # ── Header ──
    lines.append(f"{'=' * 80}")
    lines.append(f"  IMPORT USAGE REPORT — {now:%Y-%m-%d %H:%M}")
    lines.append(f"{'=' * 80}")
    lines.append(f"  Scanned directory: {BIN_DIR}")
    lines.append(f"  Files scanned: {len(per_file_data)}")
    lines.append("")

    # ── Section 1: Standard Library ──
    lines.append(f"{'─' * 80}")
    lines.append("  SECTION 1: STANDARD LIBRARY MODULES")
    lines.append(f"{'─' * 80}")
    if stdlib_counts:
        lines.append(f"\n  {'Module':<35} {'Total Calls':<15} {'Files':<10}")
        lines.append("  " + "-" * 70)
        for mod in sorted(stdlib_counts, key=lambda m: -stdlib_counts[m]):
            files_used = len(stdlib_files.get(mod, set()))
            lines.append(f"  {mod:<35} {stdlib_counts[mod]:<15} {files_used:<10}")
        lines.append(f"\n  Total stdlib modules used: {len(stdlib_counts)}")
    else:
        lines.append("  (none)")

    # ── Section 2: Third-Party Packages ──
    lines.append(f"\n{'─' * 80}")
    lines.append("  SECTION 2: THIRD-PARTY PACKAGES")
    lines.append(f"{'─' * 80}")
    if thirdparty_counts:
        lines.append(f"\n  {'Package':<35} {'Total Calls':<15} {'Files':<10}")
        lines.append("  " + "-" * 70)
        for mod in sorted(thirdparty_counts, key=lambda m: -thirdparty_counts[m]):
            files_used = len(thirdparty_files.get(mod, set()))
            lines.append(f"  {mod:<35} {thirdparty_counts[mod]:<15} {files_used:<10}")
        lines.append(f"\n  Total third-party packages used: {len(thirdparty_counts)}")
    else:
        lines.append("  (none)")

    # ── Section 3: Custom 'dh' Package ──
    lines.append(f"\n{'─' * 80}")
    lines.append(f"  SECTION 3: CUSTOM '{PACKAGE}' PACKAGE")
    lines.append(f"{'─' * 80}")
    if dh_counts:
        lines.append(f"\n  {'Function':<35} {'Total Calls':<15} {'Files':<10}")
        lines.append("  " + "-" * 70)
        for func in sorted(dh_counts, key=lambda f: -dh_counts[f]):
            files_used = len(dh_files.get(func, set()))
            lines.append(f"  {func:<35} {dh_counts[func]:<15} {files_used:<10}")
        lines.append(f"\n  Total dh functions used: {len(dh_counts)}")
    else:
        lines.append("  (none)")

    # ── Section 4: Per-File Breakdown ──
    lines.append(f"\n{'─' * 80}")
    lines.append("  SECTION 4: PER-FILE BREAKDOWN")
    lines.append(f"{'─' * 80}")

    for fname, module_calls in sorted(per_file_data, key=lambda x: -sum(sum(c.values()) for c in x[1].values())):
        total_calls = sum(sum(c.values()) for c in module_calls.values())
        lines.append(f"\n  📄 {fname}  ({total_calls} total calls)")

        # Group by category
        stdlib_in_file = {}
        thirdparty_in_file = {}
        dh_in_file = {}

        for mod, func_calls in module_calls.items():
            top_level = mod.split(".")[0]
            if top_level == PACKAGE:
                dh_in_file[mod] = func_calls
            elif is_stdlib(mod, stdlib_set):
                stdlib_in_file[mod] = func_calls
            else:
                thirdparty_in_file[mod] = func_calls

        if stdlib_in_file:
            lines.append("    [stdlib]")
            for mod in sorted(stdlib_in_file):
                funcs = stdlib_in_file[mod]
                total = sum(funcs.values())
                lines.append(f"      {mod:<30} {total} call(s)")
                for func, count in sorted(funcs.items(), key=lambda x: -x[1]):
                    if count > 0:
                        lines.append(f"        {func:<28} {count} time(s)")

        if thirdparty_in_file:
            lines.append("    [third-party]")
            for mod in sorted(thirdparty_in_file):
                funcs = thirdparty_in_file[mod]
                total = sum(funcs.values())
                lines.append(f"      {mod:<30} {total} call(s)")
                for func, count in sorted(funcs.items(), key=lambda x: -x[1]):
                    if count > 0:
                        lines.append(f"        {func:<28} {count} time(s)")

        if dh_in_file:
            lines.append(f"    [{PACKAGE}]")
            for mod in sorted(dh_in_file):
                funcs = dh_in_file[mod]
                total = sum(funcs.values())
                lines.append(f"      {mod:<30} {total} call(s)")
                for func, count in sorted(funcs.items(), key=lambda x: -x[1]):
                    if count > 0:
                        lines.append(f"        {func:<28} {count} time(s)")

    # ── Footer ──
    lines.append("")
    lines.append(f"{'=' * 80}")
    lines.append("  END OF REPORT")
    lines.append(f"{'=' * 80}")

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    if not BIN_DIR.is_dir():
        print(f"❌ {BIN_DIR} does not exist or is not a directory.")
        sys.exit(1)

    py_files = sorted(BIN_DIR.glob("*.py"))
    if not py_files:
        print(f"⚠️  No .py files found in {BIN_DIR}.")
        REPORT.write_text(f"No .py files found in {BIN_DIR}.\n")
        return

    print(f"🔍 Scanning {len(py_files)} Python file(s) in {BIN_DIR} ...")
    print("   Building stdlib list (this may take a moment)...")

    stdlib_set = get_stdlib_modules()
    print(f"   Detected {len(stdlib_set)} stdlib modules\n")

    per_file_data: list[tuple[str, dict[str, dict[str, int]]]] = []

    for f in py_files:
        imports = extract_imports(f)
        if not imports:
            continue

        calls = count_calls(f, imports)
        if calls:
            per_file_data.append((f.name, calls))

    if not per_file_data:
        print("✅ No imports found in any script.")
        REPORT.write_text(f"No imports found in {BIN_DIR}.\n")
        return

    report_text = generate_report(per_file_data, stdlib_set)
    REPORT.write_text(report_text, encoding="utf-8")

    print(report_text)
    print(f"\n✅ Report saved to {REPORT}")


if __name__ == "__main__":
    main()
