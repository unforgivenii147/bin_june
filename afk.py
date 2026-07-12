#!/data/data/com.termux/files/usr/bin/env python


"""
unused_imports.py — detect (and optionally fix) unused imports in Python files.

Supports:
  • Multiple file(s) and/or directory(s) as input
  • Recursive directory scanning via pathlib
  • Parallel processing via multiprocessing
  • .whl and .tar.zst archive scanning
  • --autofix with .bak backup
  • --dry-run and --verbose modes
"""

import argparse
import ast
import multiprocessing
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


@dataclass
class UnusedImport:
    lineno: int
    col_offset: int
    statement: str
    names: list[str]


@dataclass
class FileReport:
    path: str
    unused: list[UnusedImport] = field(default_factory=list)
    error: Optional[str] = None


def _dotted(name: str, asname: Optional[str]) -> tuple[str, str]:
    bound = asname if asname else name.split(".")[0]
    full = asname if asname else name
    return bound, full


def _collect_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            root = child
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                names.add(root.id)
    return names


def _collect_string_uses(tree: ast.AST) -> set[str]:
    tokens: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for tok in re.split(r"[,.;:\s\[\](){}\"\'<>]+", node.value):
                tok = tok.strip()
                if tok and tok.isidentifier():
                    tokens.add(tok)
    return tokens


def _collect_all_names(tree: ast.AST) -> Set[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        names = set()
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                names.add(elt.value)
                        return names
    return set()


def _is_under_type_checking(node: ast.AST, tree: ast.AST) -> bool:
    parent: dict[int, ast.AST] = {}
    for p in ast.walk(tree):
        for child in ast.iter_child_nodes(p):
            parent[id(child)] = p
    current = parent.get(id(node))
    while current is not None:
        if isinstance(current, ast.If):
            test = current.test
            if (
                isinstance(test, ast.Name)
                and test.id == "TYPE_CHECKING"
                or isinstance(test, ast.Attribute)
                and test.attr == "TYPE_CHECKING"
            ):
                return True
        current = parent.get(id(current))
    return False


def _is_module_used_in_docstring(tree: ast.AST, module_name: str) -> bool:
    docstring = ast.get_docstring(tree)
    if docstring:
        return module_name in docstring
    return False


def _get_re_export_names(tree: ast.AST) -> Set[str]:
    re_exports = set()
    __all__names = _collect_all_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                if name in __all__names:
                    re_exports.add(name)
    return re_exports


def analyse_source(source: str, display_path: str) -> FileReport:
    report = FileReport(path=display_path)
    try:
        tree = ast.parse(source, filename=display_path)
    except SyntaxError as exc:
        report.error = f"SyntaxError: {exc}"
        return report
    lines = source.splitlines()
    used_names: set[str] = set()
    import_nodes: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_nodes.append(node)
        else:
            used_names |= _collect_names(node)
    used_names |= _collect_string_uses(tree)
    re_exports = _get_re_export_names(tree)
    used_names |= re_exports
    is_init = display_path.endswith("__init__.py")
    for node in import_nodes:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if _is_under_type_checking(node, tree):
            continue
        if isinstance(node, ast.ImportFrom) and node.module:
            if _is_module_used_in_docstring(tree, node.module):
                continue
        unused_names: list[str] = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound, full = _dotted(alias.name, alias.asname)
                if bound not in used_names and (not is_init or bound not in re_exports):
                    unused_names.append(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if is_init and node.level and node.level > 0:
                continue
            for alias in node.names:
                if alias.name == "*":
                    break
                bound, full = _dotted(alias.name, alias.asname)
                if bound not in used_names and (not is_init or bound not in re_exports):
                    unused_names.append(alias.asname or alias.name)
        if unused_names:
            raw_line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
            report.unused.append(
                UnusedImport(
                    lineno=node.lineno, col_offset=node.col_offset, statement=raw_line.strip(), names=unused_names
                )
            )
    return report


def _remove_names_from_import(line: str, names_to_remove: set[str]) -> Optional[str]:
    stripped = line.strip()
    if stripped.startswith("import ") and not stripped.startswith("from "):
        parts = stripped[len("import ") :].split(",")
        kept = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                full_name = part.split(" as ")[0].strip()
                alias = part.split(" as ")[1].strip()
                check_name = alias
            else:
                full_name = part
                check_name = part.split(".")[0]
            if check_name not in names_to_remove:
                kept.append(part)
        if not kept:
            return None
        indent = line[: len(line) - len(line.lstrip())]
        return indent + "import " + ", ".join(kept) + "\n"
    if stripped.startswith("from ") and " import " in stripped:
        prefix, import_part = stripped.split(" import ", 1)
        if import_part.strip().startswith("("):
            paren_content = import_part.strip()[1:]
            if paren_content.endswith(")"):
                paren_content = paren_content[:-1]
            parts = paren_content.split(",")
            is_parenthesized = True
        else:
            parts = import_part.split(",")
            is_parenthesized = False
        kept = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                alias = part.split(" as ")[1].strip()
                check_name = alias
            else:
                check_name = part.strip()
            if check_name not in names_to_remove:
                kept.append(part)
        if not kept:
            return None
        indent = line[: len(line) - len(line.lstrip())]
        if is_parenthesized:
            return indent + prefix + " import (" + ", ".join(kept) + ")\n"
        else:
            return indent + prefix + " import " + ", ".join(kept) + "\n"
    return line


def fix_source(source: str, report: FileReport) -> Optional[str]:
    if not report.unused:
        return None
    lines = source.splitlines(keepends=True)
    removals: dict[int, set[str]] = {}
    for ui in report.unused:
        removals.setdefault(ui.lineno, set()).update(ui.names)
    new_lines: list[str] = []
    for idx, line in enumerate(lines, start=1):
        if idx in removals:
            replacement = _remove_names_from_import(line, removals[idx])
            if replacement is None:
                continue
            new_lines.append(replacement)
        else:
            new_lines.append(line)
    return "".join(new_lines)


def _process_file(args: tuple) -> FileReport:
    path_str, display_path = args
    try:
        source = Path(path_str).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return FileReport(path=display_path, error=str(exc))
    return analyse_source(source, display_path)


def _process_source_tuple(args: tuple) -> FileReport:
    source, display_path = args
    return analyse_source(source, display_path)


def _extract_py_from_whl(archive: Path) -> list[tuple[str, str]]:
    results = []
    try:
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                if name.endswith(".py"):
                    try:
                        source = zf.read(name).decode("utf-8", errors="replace")
                        results.append((source, f"{archive}::{name}"))
                    except Exception:
                        pass
    except zipfile.BadZipFile as exc:
        results.append(("", f"{archive}::ERROR:{exc}"))
    return results


def _extract_py_from_tar_zst(archive: Path) -> list[tuple[str, str]]:
    results = []
    try:
        import zstandard

        with archive.open("rb") as fh:
            dctx = zstandard.ZstdDecompressor()
            with tempfile.TemporaryFile() as tmp:
                dctx.copy_stream(fh, tmp)
                tmp.seek(0)
                with tarfile.open(fileobj=tmp) as tf:
                    for member in tf.getmembers():
                        if member.name.endswith(".py") and member.isfile():
                            try:
                                f = tf.extractfile(member)
                                if f:
                                    source = f.read().decode("utf-8", errors="replace")
                                    results.append((source, f"{archive}::{member.name}"))
                            except Exception:
                                pass
    except ImportError:
        try:
            with tarfile.open(archive, "r:zst") as tf:
                for member in tf.getmembers():
                    if member.name.endswith(".py") and member.isfile():
                        try:
                            f = tf.extractfile(member)
                            if f:
                                source = f.read().decode("utf-8", errors="replace")
                                results.append((source, f"{archive}::{member.name}"))
                        except Exception:
                            pass
        except Exception as exc:
            results.append(("", f"{archive}::ERROR:{exc}"))
    except Exception as exc:
        results.append(("", f"{archive}::ERROR:{exc}"))
    return results


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
CYAN = "\x1b[36m"
GREEN = "\x1b[32m"


def _coloured(text: str, code: str, use_colour: bool) -> str:
    return f"{code}{text}{RESET}" if use_colour else text


def print_report(reports: list[FileReport], verbose: bool, use_colour: bool) -> int:
    total = 0
    files_with_issues: list[FileReport] = [r for r in reports if r.unused or r.error]
    if not files_with_issues:
        print(_coloured("✓ No unused imports found.", GREEN, use_colour))
        return 0
    for report in files_with_issues:
        if report.error:
            print(_coloured(f"ERROR  {report.path}: {report.error}", RED, use_colour))
            continue
        first = True
        for ui in report.unused:
            total += 1
            label = _coloured(report.path, BOLD, use_colour) if first else " " * len(report.path)
            lineno_str = _coloured(f"line {ui.lineno:>4}", CYAN, use_colour)
            stmt_str = _coloured(ui.statement, YELLOW, use_colour)
            names_note = ""
            if verbose and len(ui.names) < len(ui.statement.split(",")):
                names_note = "  [unused: " + _coloured(", ".join(ui.names), RED, use_colour) + "]"
            print(f"{label}  -->  {lineno_str}  {stmt_str}{names_note}")
            first = False
    print()
    print(_coloured(f"Found {total} unused import(s) across {len(files_with_issues)} file(s).", BOLD, use_colour))
    return total


def collect_tasks(
    paths: list[Path], exclude_patterns: Optional[list[str]] = None
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    file_tasks: list[tuple[str, str]] = []
    source_tasks: list[tuple[str, str]] = []
    if exclude_patterns is None:
        exclude_patterns = []
    exclude_re = re.compile(r"|".join(exclude_patterns)) if exclude_patterns else None
    for path in paths:
        if path.is_file():
            if exclude_re and exclude_re.search(str(path)):
                continue
            suffix = path.suffix.lower()
            name = path.name.lower()
            if suffix == ".py":
                file_tasks.append((str(path), str(path)))
            elif suffix == ".whl":
                source_tasks.extend(_extract_py_from_whl(path))
            elif name.endswith(".tar.zst"):
                source_tasks.extend(_extract_py_from_tar_zst(path))
        elif path.is_dir():
            for p in path.rglob("*"):
                if not p.is_file():
                    continue
                if exclude_re and exclude_re.search(str(p)):
                    continue
                suffix = p.suffix.lower()
                name = p.name.lower()
                if suffix == ".py":
                    file_tasks.append((str(p), str(p)))
                elif suffix == ".whl":
                    source_tasks.extend(_extract_py_from_whl(p))
                elif name.endswith(".tar.zst"):
                    source_tasks.extend(_extract_py_from_tar_zst(p))
        else:
            print(f"Warning: '{path}' does not exist, skipping.", file=sys.stderr)
    return file_tasks, source_tasks


def run(
    paths: list[Path], workers: int, autofix: bool, dry_run: bool, verbose: bool, exclude: Optional[list[str]] = None
) -> int:
    use_colour = sys.stdout.isatty()
    if verbose:
        print(f"Scanning {len(paths)} path(s) with {workers} worker(s) …\n")
    file_tasks, source_tasks = collect_tasks(paths, exclude)
    if verbose:
        print(f"  {len(file_tasks)} .py file(s), {len(source_tasks)} archive member(s) queued.\n")
    reports: list[FileReport] = []
    with multiprocessing.Pool(processes=workers) as pool:
        if file_tasks:
            if verbose:
                results = pool.imap_unordered(_process_file, file_tasks)
                for i, report in enumerate(results, 1):
                    reports.append(report)
                    if i % 10 == 0 or i == len(file_tasks):
                        print(f"  Processed {i}/{len(file_tasks)} files...", end="\r")
                if file_tasks:
                    print(f"  Processed {len(file_tasks)}/{len(file_tasks)} files.    ")
            else:
                reports.extend(pool.map(_process_file, file_tasks))
        if source_tasks:
            reports.extend(pool.map(_process_source_tuple, source_tasks))
    reports.sort(key=lambda r: r.path)
    total = print_report(reports, verbose=verbose, use_colour=use_colour)
    if autofix and total > 0:
        fixed_count = 0
        for report in reports:
            if not report.unused or report.error:
                continue
            if "::" in report.path:
                if verbose:
                    print(f"  skip autofix for archive member: {report.path}")
                continue
            p = Path(report.path)
            try:
                source = p.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"  cannot read {p}: {exc}", file=sys.stderr)
                continue
            new_source = fix_source(source, report)
            if new_source is None:
                continue
            try:
                ast.parse(new_source, filename=str(p))
            except SyntaxError as exc:
                print(
                    f"  {_coloured('SKIP', RED, use_colour)} autofix on {p} — result failed to parse: {exc}",
                    file=sys.stderr,
                )
                continue
            if dry_run:
                print(f"  {_coloured('[dry-run]', CYAN, use_colour)} would fix {p}")
                fixed_count += 1
                continue
            bak = p.with_suffix(p.suffix + ".bak")
            counter = 1
            while bak.exists():
                bak = p.with_suffix(f"{p.suffix}.bak.{counter}")
                counter += 1
            shutil.copy2(p, bak)
            p.write_text(new_source, encoding="utf-8")
            fixed_count += 1
            if verbose:
                print(f"  {_coloured('fixed', GREEN, use_colour)} {p}  (backup → {bak})")
        action = "would fix" if dry_run else "fixed"
        print(f"\n{action.capitalize()} {fixed_count} file(s).")
    elif dry_run and total == 0:
        print("Nothing to fix.")
    return 1 if total > 0 else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report (and optionally remove) unused imports in Python files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # scan current directory
  %(prog)s src/                     # scan a specific directory
  %(prog)s file1.py file2.py        # scan specific files
  %(prog)s src/ tests/              # scan multiple directories
  %(prog)s file.py src/             # mix files and directories
  %(prog)s -a                       # autofix in-place (with .bak)
  %(prog)s -a --dry-run             # preview fixes without writing
  %(prog)s -v --workers 4           # verbose output, 4 workers
  %(prog)s --exclude "test_.*"      # exclude test files
  %(prog)s --exclude "venv" --exclude ".git"  # exclude multiple patterns
""",
    )
    parser.add_argument(
        "paths", nargs="*", default=["."], help="Files and/or directories to scan (default: current directory)"
    )
    parser.add_argument(
        "-a", "--autofix", action="store_true", help="Remove unused imports in-place; creates .bak backups"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without writing files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print extra progress and per-name details")
    parser.add_argument(
        "--workers", type=int, default=8, metavar="N", help="Number of parallel worker processes (default: 8)"
    )
    parser.add_argument(
        "--exclude",
        action="append",
        metavar="PATTERN",
        help="Exclude files/directories matching regex pattern (can be used multiple times)",
    )
    parser.add_argument("--ignore-init", action="store_true", help="Ignore __init__.py files (treat imports as used)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    paths = [Path(p).resolve() for p in args.paths]
    valid_paths = []
    for p in paths:
        if p.exists():
            valid_paths.append(p)
        else:
            print(f"Warning: '{p}' does not exist, skipping.", file=sys.stderr)
    if not valid_paths:
        parser.error("No valid files or directories to scan.")
    if args.dry_run and not args.autofix:
        args.autofix = True
    if args.no_color:
        global RESET, BOLD, YELLOW, RED, CYAN, GREEN
        RESET = BOLD = YELLOW = RED = CYAN = GREEN = ""
    sys.exit(
        run(
            paths=valid_paths,
            workers=max(1, args.workers),
            autofix=args.autofix,
            dry_run=args.dry_run,
            verbose=args.verbose,
            exclude=args.exclude,
        )
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
