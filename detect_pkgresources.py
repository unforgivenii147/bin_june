#!/data/data/com.termux/files/home/.local/bin/python
import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
    }
)

DIRECT_REPLACEMENTS = (
    (
        re.compile(r"\bpkg_resources\.get_distribution\((?P<arg>[^()\n]+)\)\.version"),
        r"importlib.metadata.version(\g<arg>)",
        "Replaced pkg_resources.get_distribution(...).version.",
    ),
    (
        re.compile(r"\bpkg_resources\.get_distribution\((?P<arg>[^()\n]+)\)"),
        r"importlib.metadata.distribution(\g<arg>)",
        "Replaced pkg_resources.get_distribution(...).",
    ),
    (
        re.compile(r"\bpkg_resources\.parse_version\("),
        "packaging.version.Version(",
        "Replaced pkg_resources.parse_version(...).",
    ),
)

FROM_IMPORT_REPLACEMENTS = (
    (
        "get_distribution",
        "import importlib.metadata",
        "importlib.metadata.distribution",
    ),
    (
        "parse_version",
        "import packaging.version",
        "packaging.version.Version",
    ),
)


@dataclass(slots=True)
class FileResult:
    path: Path
    pkg_resources_imports: int = 0
    pkg_resources_references: int = 0
    syntax_error: str | None = None
    error: str | None = None
    changed: bool = False
    fixes: tuple[str, ...] = ()
    validation_error: str | None = None

    @property
    def found(self) -> bool:
        return self.pkg_resources_imports > 0 or self.pkg_resources_references > 0


class PkgResourcesVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports = 0
        self.references = 0
        self.module_aliases: set[str] = set()
        self.imported_names: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "pkg_resources":
                self.imports += 1
                self.module_aliases.add(alias.asname or "pkg_resources")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module != "pkg_resources":
            return
        self.imports += 1
        for alias in node.names:
            if alias.name == "*":
                continue
            self.imported_names.add(alias.asname or alias.name)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id in self.module_aliases:
            self.references += 1
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self.imported_names:
            self.references += 1


def iter_python_files(inputs: list[Path]) -> Iterator[Path]:
    seen: set[Path] = set()
    for input_path in inputs:
        try:
            path = input_path.expanduser().absolute()
        except OSError as exc:
            print(f"ERROR   {input_path}: could not access path: {exc}")
            continue
        if path.is_file():
            if path.suffix == ".py" and path not in seen:
                seen.add(path)
                yield path
            continue
        if not path.is_dir():
            print(f"ERROR   {path}: path does not exist or is not accessible")
            continue
        yield from walk_python_files(path, seen)


def walk_python_files(directory: Path, seen: set[Path]) -> Iterator[Path]:
    try:
        for child in directory.iterdir():
            if child.is_dir():
                if child.name in EXCLUDED_DIRS or child.name.startswith("."):
                    continue
                yield from walk_python_files(child, seen)
                continue
            if child.suffix != ".py":
                continue
            if child not in seen:
                seen.add(child)
                yield child
    except OSError as exc:
        print(f"ERROR   {directory}: traversal failed: {exc}")


def detect_usage(source: str) -> tuple[int, int, str | None]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return 0, 0, f"{exc.msg} (line {exc.lineno}, column {exc.offset})"
    visitor = PkgResourcesVisitor()
    visitor.visit(tree)
    return visitor.imports, visitor.references, None


def has_pkg_resources_module_usage(source: str) -> bool:
    return bool(re.search(r"\bpkg_resources\s*\.", source))


def add_imports(source: str, imports: list[str]) -> str:
    if not imports:
        return source
    unique_imports: list[str] = []
    for import_line in imports:
        if import_line not in source and import_line not in unique_imports:
            unique_imports.append(import_line)
    if not unique_imports:
        return source
    lines = source.splitlines(keepends=True)
    insertion_index = 0
    if lines and lines[0].startswith("#!"):
        insertion_index = 1
    if len(lines) > insertion_index and re.match(r"^[ \t]*#.*coding[:=]", lines[insertion_index]):
        insertion_index += 1
    import_block = "".join(f"{line}\n" for line in unique_imports)
    lines.insert(insertion_index, import_block)
    return "".join(lines)


def replace_from_import_usage(source: str) -> tuple[str, list[str], list[str]]:
    required_imports: list[str] = []
    fixes: list[str] = []
    for imported_name, required_import, replacement_prefix in FROM_IMPORT_REPLACEMENTS:
        pattern = re.compile(rf"(?m)^from\s+pkg_resources\s+import\s+{imported_name}\s*$")
        if not pattern.search(source):
            continue
        local_pattern = re.compile(rf"\b{imported_name}\(")
        if imported_name == "get_distribution":
            source, version_count = re.subn(
                rf"\b{imported_name}\((?P<arg>[^()\n]+)\)\.version",
                rf"importlib.metadata.version(\g<arg>)",
                source,
            )
            if version_count:
                fixes.append(f"Replaced {version_count} get_distribution(...).version call(s).")
            source, distribution_count = re.subn(
                rf"\b{imported_name}\((?P<arg>[^()\n]+)\)",
                rf"importlib.metadata.distribution(\g<arg>)",
                source,
            )
            if distribution_count:
                fixes.append(f"Replaced {distribution_count} get_distribution(...) call(s).")
        elif imported_name == "parse_version":
            source, count = re.subn(
                rf"\b{imported_name}\(",
                f"{replacement_prefix}(",
                source,
            )
            if count:
                fixes.append(f"Replaced {count} parse_version(...) call(s).")
        if not local_pattern.search(source):
            source = pattern.sub("", source)
            required_imports.append(required_import)
            fixes.append(f"Removed from pkg_resources import {imported_name}.")
    return source, required_imports, fixes


def apply_fixes(source: str) -> tuple[str, tuple[str, ...]]:
    updated = source
    fixes: list[str] = []
    required_imports: list[str] = []
    for pattern, replacement, description in DIRECT_REPLACEMENTS:
        updated, count = pattern.subn(replacement, updated)
        if count:
            fixes.append(f"{description} Count: {count}.")
    updated, from_imports, from_fixes = replace_from_import_usage(updated)
    required_imports.extend(from_imports)
    fixes.extend(from_fixes)
    if "importlib.metadata." in updated:
        required_imports.append("import importlib.metadata")
    if "packaging.version." in updated:
        required_imports.append("import packaging.version")
    if not has_pkg_resources_module_usage(updated):
        updated, removed = re.subn(
            r"(?m)^([ \t]*)import\s+pkg_resources(?:\s+as\s+\w+)?\s*\n?",
            "",
            updated,
        )
        if removed:
            fixes.append("Removed unused import pkg_resources.")
    updated = add_imports(updated, required_imports)
    if required_imports:
        added = [import_line for import_line in dict.fromkeys(required_imports) if import_line in updated]
        if added:
            fixes.append(f"Ensured replacement imports: {', '.join(added)}.")
    return updated, tuple(fixes)


def read_source(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    return raw.decode("utf-8"), "utf-8"


def validate_python_source(source: str, path: Path) -> str | None:
    try:
        ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        location = f"line {exc.lineno}, column {exc.offset}"
        return f"{exc.msg} ({location})"
    return None


def process_file(path: Path, auto_fix: bool) -> FileResult:
    result = FileResult(path=path)
    try:
        source, encoding = read_source(path)
    except UnicodeDecodeError as exc:
        result.error = f"UTF-8 decode error: {exc}"
        return result
    except OSError as exc:
        result.error = f"Read failed: {exc}"
        return result

    imports, references, syntax_error = detect_usage(source)
    result.pkg_resources_imports = imports
    result.pkg_resources_references = references
    result.syntax_error = syntax_error

    if syntax_error or not auto_fix or not result.found:
        return result

    updated, fixes = apply_fixes(source)
    if updated == source:
        return result

    validation_error = validate_python_source(updated, path)
    if validation_error:
        result.validation_error = validation_error
        result.error = f"Generated replacement was not written because syntax validation failed: {validation_error}"
        return result

    try:
        path.write_text(updated, encoding=encoding, newline="")
        result.changed = True
        result.fixes = fixes
    except OSError as exc:
        result.error = f"Write failed: {exc}"
    return result


def relative_display_path(path: Path, base_dir: Path) -> str:
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return os.path.relpath(path, base_dir)


def find_checker() -> tuple[str, ...] | None:
    if shutil.which("ty"):
        return ("ty", "check")
    if shutil.which("ruff"):
        return ("ruff", "check")
    if shutil.which("pyright"):
        return ("pyright",)
    return None


def run_checker(paths: list[Path], *, required: bool = False) -> int:
    if not paths:
        return 0

    checker = find_checker()
    if checker is None:
        message = "No supported checker found. Install ty, ruff, or pyright for post-rewrite validation."
        if required:
            print(f"ERROR {message}", file=sys.stderr)
            return 1
        print(f"WARNING {message}", file=sys.stderr)
        return 0

    command = [*checker, *(str(path) for path in paths)]
    print(f"\nValidating {len(paths)} changed file(s): {' '.join(command)}")
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
        )
    except OSError as exc:
        print(f"ERROR Could not run {' '.join(checker)}: {exc}", file=sys.stderr)
        return 1

    if completed.returncode != 0:
        print(
            f"ERROR {' '.join(checker)} failed with exit code {completed.returncode}.",
            file=sys.stderr,
        )
        return completed.returncode
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect and optionally migrate pkg_resources usage.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files and/or directories to scan. Defaults to the current directory.",
    )
    parser.add_argument(
        "-a",
        "--auto-fix",
        action="store_true",
        help="Apply conservative automatic migrations in place.",
    )
    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=os.cpu_count() or 1,
        help="Number of worker processes (default: CPU count).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Run ty, ruff, or pyright against modified files after applying fixes. "
            "Checker preference: ty, then ruff, then pyright."
        ),
    )
    parser.add_argument(
        "--require-checker",
        action="store_true",
        help="Fail if --check is used but ty, ruff, and pyright are unavailable.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.workers < 1:
        print("ERROR   --workers must be at least 1")
        return 2

    base_dir = Path.cwd().absolute()
    inputs = args.paths or [base_dir]
    files = list(iter_python_files(inputs))

    if not files:
        print("No Python files found.")
        return 0

    workers = min(args.workers, len(files))
    print(f"Scanning {len(files)} Python file(s) with {workers} worker(s)...")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(
            executor.map(
                process_file,
                files,
                [args.auto_fix] * len(files),
                chunksize=max(1, len(files) // (workers * 4)),
            )
        )

    found_files = 0
    changed_files = 0
    errors = 0
    total_imports = 0
    total_references = 0

    for result in sorted(results, key=lambda item: str(item.path)):
        total_imports += result.pkg_resources_imports
        total_references += result.pkg_resources_references
        display_path = relative_display_path(result.path, base_dir)

        if result.error:
            errors += 1
            print(f"ERROR   {display_path}: {result.error}")
            continue

        if result.syntax_error:
            errors += 1
            print(f"INVALID {display_path}: syntax error: {result.syntax_error}")
            continue

        if not result.found:
            continue

        found_files += 1
        if result.changed:
            changed_files += 1
            status = "FIXED"
        else:
            status = "FOUND"
        print(
            f"{status:<7} {display_path} | "
            f"imports={result.pkg_resources_imports} "
            f"references={result.pkg_resources_references}"
        )
        for fix in result.fixes:
            print(f"        -> {fix}")

    # Run checker on changed files
    changed_paths = [result.path for result in results if result.changed and result.error is None]

    checker_exit_code = 0
    if args.check and changed_paths:
        checker_exit_code = run_checker(
            changed_paths,
            required=args.require_checker,
        )

    print("\nSummary")
    print(f"  Files scanned:       {len(results)}")
    print(f"  Files with usage:    {found_files}")
    print(f"  Imports found:       {total_imports}")
    print(f"  References found:    {total_references}")
    print(f"  Files modified:      {changed_files}")
    print(f"  Errors:              {errors}")
    if args.check:
        print(f"  External validation: {'passed' if checker_exit_code == 0 else 'failed'}")

    return 1 if errors or checker_exit_code else 0


if __name__ == "__main__":
    raise SystemExit(main())
