#!/data/data/com.termux/files/usr/bin/env python
"""
unused_imports.py — detect and optionally remove unused imports from Python source files.

Supports individual files, directories (recursive), and Python package archives (.whl, .tar.zst).

Usage examples:
  python unused_imports.py src/
  python unused_imports.py src/ --autofix
  python unused_imports.py src/ --dry-run
  python unused_imports.py mypackage.whl
  python unused_imports.py . --exclude tests/ --workers 4 --verbose
  python unused_imports.py file.py --autofix --no-color
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import re
import sys
import tarfile
import zipfile
from dataclasses import dataclass, field
from multiprocessing import Pool
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Optional zstandard support
# ---------------------------------------------------------------------------
try:
    import zstandard as zstd  # type: ignore[import-untyped]

    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False


# ===========================================================================
# Data structures
# ===========================================================================


@dataclass
class UnusedImport:
    """One unused-import occurrence inside a source file."""

    lineno: int
    col_offset: int
    original_stmt: str  # the exact source line(s) of the import
    unused_names: list[str]  # names within the statement that are unused


@dataclass
class FileReport:
    """Analysis result for a single source file (real or virtual archive member)."""

    path: str  # real path or  archive::member
    unused: list[UnusedImport] = field(default_factory=list)
    error: str | None = None


# ===========================================================================
# ANSI colour helpers
# ===========================================================================

_USE_COLOR = True  # module-level flag; set by CLI before spawning workers


def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(t: str) -> str:
    return _c("1", t)


def cyan(t: str) -> str:
    return _c("36", t)


def yellow(t: str) -> str:
    return _c("33", t)


def red(t: str) -> str:
    return _c("31", t)


def green(t: str) -> str:
    return _c("32", t)


def dim(t: str) -> str:
    return _c("2", t)


# ===========================================================================
# Import-analysis engine
# ===========================================================================


def _is_under_type_checking(node: ast.AST, type_checking_blocks: set[int]) -> bool:
    """Return True when *node* lives inside an  if TYPE_CHECKING:  block."""
    return getattr(node, "lineno", -1) in type_checking_blocks


def _collect_type_checking_line_ranges(tree: ast.Module) -> set[int]:
    """
    Walk top-level if-blocks and collect line numbers of their bodies when the
    test is `TYPE_CHECKING` or `typing.TYPE_CHECKING`.
    """
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if is_tc:
            for child in ast.walk(node):
                if hasattr(child, "lineno"):
                    lines.add(child.lineno)
    return lines


def _collect_all_entries(tree: ast.Module) -> set[str]:
    """Return names listed in  __all__ = [...]  at module level."""
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            names.add(elt.value)
    return names


def _collect_used_names(tree: ast.Module) -> set[str]:
    """
    Collect every identifier that is *referenced* (not defined) in *tree*.

    Covers:
      • ast.Name   — plain identifiers
      • ast.Attribute — the root name of  a.b.c  chains
      • string literals — for forward references / TYPE_CHECKING strings
    """
    used: set[str] = set()

    for node in ast.walk(tree):
        # Plain name reference  (Load context only — Store/Del are definitions)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)

        # Attribute access  mod.func()  → capture "mod"
        elif isinstance(node, ast.Attribute):
            # Walk down to the root Name
            root = node
            while isinstance(root, ast.Attribute):
                root = root.value  # type: ignore[assignment]
            if isinstance(root, ast.Name):
                used.add(root.id)

        # String literals — forward references, dynamic imports, docs
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Cheap heuristic: extract bare identifiers from the string
            for tok in re.findall(r"\b([A-Za-z_]\w*)\b", node.value):
                used.add(tok)

    return used


def _import_aliases(node: ast.Import | ast.ImportFrom) -> list[tuple[str, str]]:
    """
    Return (original_name, local_name) pairs for every name in the statement.
    For  import os.path as p  →  ("os.path", "p")
    For  from x import y      →  ("y", "y")
    For  from x import y as z →  ("y", "z")
    """
    pairs: list[tuple[str, str]] = []
    for alias in node.names:
        original = alias.name
        local = alias.asname if alias.asname else alias.name.split(".")[0](0)
        pairs.append((original, local))
    return pairs


def analyze_source(
    source: str,
    path: str,
    *,
    is_init: bool = False,
    ignore_init: bool = False,
) -> FileReport:
    """
    Parse *source* and return a :class:`FileReport` with all unused imports.

    Parameters
    ----------
    source:
        Full Python source text.
    path:
        Display path (may be a virtual  archive::member  string).
    is_init:
        Whether the file is an  __init__.py.
    ignore_init:
        When True, treat every import in  __init__.py  as used.
    """
    report = FileReport(path=path)

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        report.error = f"SyntaxError: {exc}"
        return report

    # Treat all imports in __init__.py as used when requested
    if is_init and ignore_init:
        return report

    tc_lines = _collect_type_checking_line_ranges(tree)
    all_entries = _collect_all_entries(tree)
    used_names = _collect_used_names(tree)

    # Grab the module docstring once (cheap string check)
    module_doc = ""
    if (
        tree.body
        and isinstance(tree.body[0](0), ast.Expr)
        and isinstance(tree.body[0](0).value, ast.Constant)
        and isinstance(tree.body[0](0).value.value, str)
    ):
        module_doc = tree.body[0](0).value.value

    source_lines = source.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue

        # Skip TYPE_CHECKING-guarded imports
        if node.lineno in tc_lines:
            continue

        # from __future__ import ...  — always skip
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue

        # from module import *  — can't analyse statically
        if any(alias.name == "*" for alias in node.names):
            continue

        # Relative imports in __init__.py are presumed to be re-exports
        if is_init and isinstance(node, ast.ImportFrom) and (node.level or 0) > 0:
            continue

        aliases = _import_aliases(node)
        unused_here: list[str] = []

        for _original, local in aliases:
            # Appears in __all__  → treated as used (re-export)
            if local in all_entries:
                continue

            # Name appears somewhere in the source text
            if local in used_names:
                continue

            # Mentioned in the module docstring (documentation reference)
            if local in module_doc:
                continue

            unused_here.append(local)

        if not unused_here:
            continue

        # Extract the original source text for this statement (may span lines)
        start = node.lineno - 1
        end = node.end_lineno  # type: ignore[attr-defined]
        original_stmt = "\n".join(source_lines[start:end])

        report.unused.append(
            UnusedImport(
                lineno=node.lineno,
                col_offset=node.col_offset,
                original_stmt=original_stmt,
                unused_names=unused_here,
            )
        )

    return report


# ===========================================================================
# Auto-fix engine
# ===========================================================================


def _remove_names_from_import_line(line: str, names_to_remove: set[str]) -> str | None:
    """
    Remove *names_to_remove* from a single-line import statement.
    Returns the rewritten line, or None if all names were removed
    (caller should delete the line entirely).
    """
    # ── import a, b, c ──────────────────────────────────────────────────────
    m = re.match(r"^(\s*import\s+)(.+)$", line)
    if m:
        prefix, rest = m.group(1), m.group(2)
        kept = [seg.strip() for seg in rest.split(",") if _alias_local_name(seg.strip()) not in names_to_remove]
        if not kept:
            return None
        return prefix + ", ".join(kept)

    # ── from x import a, b, c ───────────────────────────────────────────────
    m = re.match(r"^(\s*from\s+[\w.]+\s+import\s+)(.+)$", line)
    if m:
        prefix, rest = m.group(1), m.group(2)
        # strip trailing comment / backslash continuation
        rest_clean = re.sub(r"\s*#.*$", "", rest).rstrip(" \\")
        kept = [
            seg.strip()
            for seg in rest_clean.split(",")
            if seg.strip() and _alias_local_name(seg.strip()) not in names_to_remove
        ]
        if not kept:
            return None
        return prefix + ", ".join(kept)

    return line  # unchanged — don't understand the format


def _alias_local_name(segment: str) -> str:
    """
    Extract the local (bound) name from an alias segment like  ``X as Y``.
    Returns ``Y`` when ``as`` is present, else the raw name (without dots).
    """
    m = re.match(r"^\s*[\w.]+\s+as\s+(\w+)\s*$", segment)
    if m:
        return m.group(1)
    return segment.strip().split(".")[0].strip()


def _fix_multiline_import(block: str, names_to_remove: set[str]) -> str | None:
    """
    Handle parenthesised multi-line imports:
        from x import (
            A,
            B,
            C,
        )
    Returns rewritten block, or None to delete entirely.
    """
    # Match the from...import header and the parenthesised body
    header_m = re.match(
        r"^(\s*from\s+[\w.]+\s+import\s*$)(.*?)($.*)",
        block,
        re.DOTALL,
    )
    if not header_m:
        return None  # can't parse — leave unchanged

    prefix = header_m.group(1)
    body = header_m.group(2)
    suffix = header_m.group(3)

    kept_segments: list[str] = []
    for seg in re.split(r",\s*", body):
        seg_clean = re.sub(r"#.*", "", seg).strip()
        if not seg_clean:
            continue
        local = _alias_local_name(seg_clean)
        if local not in names_to_remove:
            kept_segments.append(seg_clean)

    if not kept_segments:
        return None

    # Reconstruct — keep parenthesised style when multiple names remain
    if len(kept_segments) == 1 and "\n" not in block:
        return f"{prefix[:-1]}{kept_segments[0]}{suffix[1:]}"
    inner = ",\n    ".join(kept_segments)
    return f"{prefix}\n    {inner},\n{suffix}"


def apply_fix(source: str, unused_imports: list[UnusedImport]) -> str:
    """
    Return a new version of *source* with all *unused_imports* removed.

    Strategy: work line-by-line; for multi-line imports, collect the block
    and rewrite it as a unit.
    """
    # Build a mapping  lineno → names_to_remove  for quick lookup
    removal_map: dict[int, set[str]] = {}
    span_map: dict[int, int] = {}  # start_lineno → end_lineno (1-based)

    for ui in unused_imports:
        ln = ui.lineno
        removal_map.setdefault(ln, set()).update(ui.unused_names)
        # Determine end line from the statement (may span multiple lines)
        span_map[ln] = ln + ui.original_stmt.count("\n")

    lines = source.splitlines(keepends=True)
    result: list[str] = []
    skip_until = -1

    i = 0
    while i < len(lines):
        lineno = i + 1  # 1-based

        if lineno <= skip_until:
            i += 1
            continue

        if lineno not in removal_map:
            result.append(lines[i])
            i += 1
            continue

        names_to_remove = removal_map[lineno]
        end_lineno = span_map[lineno]
        block = "".join(lines[i:end_lineno])  # noqa: E203

        if "(" in block and "\n" in block:
            # Multi-line parenthesised block
            fixed = _fix_multiline_import(block, names_to_remove)
        else:
            # Single-line (or backslash-continued — treat as single for now)
            single = block.strip("\n")
            fixed_line = _remove_names_from_import_line(single, names_to_remove)
            if fixed_line is None:
                fixed = None
            else:
                # Preserve original line ending
                ending = "\n" if block.endswith("\n") else ""
                fixed = fixed_line + ending

        if fixed is not None:
            result.append(fixed)

        skip_until = end_lineno
        i += 1

    return "".join(result)


# ===========================================================================
# Archive processing
# ===========================================================================


def _iter_whl_sources(archive_path: Path) -> Iterator[tuple[str, str]]:
    """Yield (virtual_path, source_text) for every .py file in a wheel."""
    try:
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                if not name.endswith(".py"):
                    continue
                virtual = f"{archive_path.name}::{name}"
                try:
                    raw = zf.read(name)
                    source = raw.decode("utf-8", errors="replace")
                    yield virtual, source
                except Exception as exc:  # noqa: BLE001
                    yield virtual, f"__ERROR__:{exc}"
    except zipfile.BadZipFile as exc:
        yield f"{archive_path.name}::?", f"__ERROR__:Bad zip: {exc}"


def _iter_tarzst_sources(archive_path: Path) -> Iterator[tuple[str, str]]:
    """
    Yield (virtual_path, source_text) for .py files in a .tar.zst archive.
    Uses *zstandard* when available, falls back to plain tarfile otherwise
    (which will fail for zstd-compressed archives — reported as error).
    """
    arc_name = archive_path.name

    def _read_tar(tf: tarfile.TarFile) -> Iterator[tuple[str, str]]:
        for member in tf.getmembers():
            if not member.name.endswith(".py"):
                continue
            virtual = f"{arc_name}::{member.name}"
            try:
                f = tf.extractfile(member)
                if f is None:
                    continue
                source = f.read().decode("utf-8", errors="replace")
                yield virtual, source
            except Exception as exc:  # noqa: BLE001
                yield virtual, f"__ERROR__:{exc}"

    try:
        if HAS_ZSTD:
            dctx = zstd.ZstdDecompressor()
            with open(archive_path, "rb") as fh:
                stream = dctx.stream_reader(fh)
                with tarfile.open(fileobj=io.BytesIO(stream.read())) as tf:
                    yield from _read_tar(tf)
        else:
            # Try plain tarfile — works for .tar.gz etc; zstd will error out
            with tarfile.open(archive_path) as tf:
                yield from _read_tar(tf)
    except Exception as exc:  # noqa: BLE001
        yield f"{arc_name}::?", f"__ERROR__:Archive error: {exc}"


# ===========================================================================
# Worker tasks (module-level so they are picklable)
# ===========================================================================

# These globals are set in worker processes via initializer
_WORKER_IGNORE_INIT: bool = False


def _worker_init(ignore_init: bool) -> None:
    global _WORKER_IGNORE_INIT
    _WORKER_IGNORE_INIT = ignore_init


def _task_analyze_file(path_str: str) -> FileReport:
    """Worker task: read and analyse a .py file from disk."""
    p = Path(path_str)
    try:
        source = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return FileReport(path=path_str, error=f"OSError: {exc}")

    is_init = p.name == "__init__.py"
    return analyze_source(source, path_str, is_init=is_init, ignore_init=_WORKER_IGNORE_INIT)


def _task_analyze_source_str(args: tuple[str, str]) -> FileReport:
    """Worker task: analyse source text passed directly (archive members)."""
    virtual_path, source = args
    if source.startswith("__ERROR__:"):
        return FileReport(path=virtual_path, error=source[len("__ERROR__:") :])
    is_init = virtual_path.endswith(("/__init__.py", "\\__init__.py"))
    return analyze_source(
        source,
        virtual_path,
        is_init=is_init,
        ignore_init=_WORKER_IGNORE_INIT,
    )


# ===========================================================================
# File discovery
# ===========================================================================


def _should_exclude(path: Path, exclude_patterns: list[re.Pattern[str]]) -> bool:
    path_str = str(path)
    return any(pat.search(path_str) for pat in exclude_patterns)


def collect_tasks(
    paths: list[Path],
    exclude_patterns: list[re.Pattern[str]],
) -> tuple[list[str], list[tuple[str, str]]]:
    """
    Expand *paths* into:
      • file_tasks  — list of .py file path strings
      • source_tasks — list of (virtual_path, source_text) for archive members

    Returns (file_tasks, source_tasks).
    """
    file_tasks: list[str] = []
    source_tasks: list[tuple[str, str]] = []

    def _add_py(p: Path) -> None:
        if not _should_exclude(p, exclude_patterns):
            file_tasks.append(str(p))

    def _add_archive(p: Path) -> None:
        if _should_exclude(p, exclude_patterns):
            return
        if p.suffix == ".whl":
            source_tasks.extend(_iter_whl_sources(p))
        elif p.name.endswith(".tar.zst"):
            source_tasks.extend(_iter_tarzst_sources(p))

    for p in paths:
        if not p.exists():
            print(
                red(f"warning: path does not exist: {p}"),
                file=sys.stderr,
            )
            continue

        if p.is_file():
            if p.suffix == ".py":
                _add_py(p)
            elif p.suffix in (".whl",) or p.name.endswith(".tar.zst"):
                _add_archive(p)
            else:
                print(
                    yellow(f"warning: skipping unrecognised file: {p}"),
                    file=sys.stderr,
                )
        elif p.is_dir():
            for child in sorted(p.rglob("*")):
                if _should_exclude(child, exclude_patterns):
                    continue
                if child.is_file():
                    if child.suffix == ".py":
                        file_tasks.append(str(child))
                    elif child.suffix == ".whl" or child.name.endswith(".tar.zst"):
                        _add_archive(child)

    return file_tasks, source_tasks


# ===========================================================================
# Reporting
# ===========================================================================


def _relative_path(path_str: str) -> str:
    """Try to make *path_str* relative to cwd for cleaner display."""
    if "::" in path_str:
        return path_str  # archive virtual path — leave as-is
    try:
        return str(Path(path_str).relative_to(Path.cwd()))
    except ValueError:
        return path_str


def print_report(
    report: FileReport,
    *,
    verbose: bool = False,
    autofix: bool = False,
    dry_run: bool = False,
) -> int:
    """
    Print findings for one file.  Returns count of unused imports found.
    """
    display = _relative_path(report.path)

    if report.error:
        print(f"  {red('error')} {bold(display)}: {red(report.error)}")
        return 0

    if not report.unused:
        if verbose:
            print(f"  {green('✓')} {dim(display)}")
        return 0

    for ui in report.unused:
        # Pad line number to 5 chars for alignment
        lineno_str = cyan(f"line {ui.lineno:>4}")
        stmt_display = yellow(ui.original_stmt.splitlines()[0])
        print(f"  {bold(display)}  -->  {lineno_str}  {stmt_display}")
        if True:  # always show unused names
            names_str = red(", ".join(ui.unused_names))
            print(f"{'':>50}  [unused: {names_str}]")

    return len(report.unused)


def print_fix_result(
    path_str: str,
    *,
    fixed: bool,
    dry_run: bool,
    error: str | None = None,
) -> None:
    display = _relative_path(path_str)
    if error:
        print(f"  {red('SKIP autofix')} {bold(display)} — result failed to parse: {error}")
    elif dry_run:
        print(f"  {cyan('would fix')} {bold(display)}")
    else:
        print(f"  {green('fixed')} {bold(display)}")


# ===========================================================================
# Main processing pipeline
# ===========================================================================


def run(
    paths: list[Path],
    *,
    autofix: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    workers: int = 8,
    exclude_patterns: list[re.Pattern[str]] | None = None,
    ignore_init: bool = False,
) -> int:
    """
    Full pipeline.  Returns exit code (0 = clean, 1 = unused imports found).
    """
    if exclude_patterns is None:
        exclude_patterns = []

    print(bold(f"\nScanning {len(paths)} path(s) with {workers} worker(s) …\n"))

    file_tasks, source_tasks = collect_tasks(paths, exclude_patterns)

    total_py = len(file_tasks)
    total_arc = len(source_tasks)
    print(f"  {cyan(str(total_py))} .py file(s), {cyan(str(total_arc))} archive member(s) queued.\n")

    if total_py + total_arc == 0:
        print(yellow("No files to analyse."))
        return 0

    # ── Run analysis in parallel ────────────────────────────────────────────
    reports: list[FileReport] = []

    with Pool(
        processes=workers,
        initializer=_worker_init,
        initargs=(ignore_init,),
    ) as pool:
        # File tasks — pass path string; worker reads from disk
        file_results = pool.imap_unordered(_task_analyze_file, file_tasks)
        # Archive tasks — pass (virtual_path, source) directly
        arc_results = pool.imap_unordered(_task_analyze_source_str, source_tasks)

        for i, rep in enumerate(file_results, 1):
            reports.append(rep)
            if verbose:
                print(
                    dim(f"  [{i}/{total_py}] analysed {_relative_path(rep.path)}"),
                    end="\r",
                )

        if verbose and total_py:
            print()  # newline after \r progress

        for rep in arc_results:
            reports.append(rep)

    # ── Sort reports for deterministic output ────────────────────────────────
    reports.sort(key=lambda r: r.path)

    # ── Print findings ───────────────────────────────────────────────────────
    total_unused = 0
    files_with_issues: set[str] = set()
    files_fixed = 0

    for report in reports:
        count = print_report(report, verbose=verbose, autofix=autofix, dry_run=dry_run)
        total_unused += count

        if count > 0:
            files_with_issues.add(report.path)

        # ── Auto-fix ──────────────────────────────────────────────────────
        if (autofix or dry_run) and count > 0 and not report.error:
            # Only real files can be fixed (not archive members)
            if "::" in report.path:
                if verbose:
                    print(dim(f"  [skip fix — archive member: {report.path}]"))
                continue

            p = Path(report.path)
            try:
                original_source = p.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print_fix_result(report.path, fixed=False, dry_run=dry_run, error=str(exc))
                continue

            new_source = apply_fix(original_source, report.unused)

            # Validate the result parses
            try:
                ast.parse(new_source, filename=report.path)
            except SyntaxError as exc:
                print_fix_result(report.path, fixed=False, dry_run=dry_run, error=str(exc))
                continue

            if dry_run:
                print_fix_result(report.path, fixed=True, dry_run=True)
            else:
                # Preserve original file permissions
                orig_stat = p.stat()
                p.write_text(new_source, encoding="utf-8")
                os.chmod(p, orig_stat.st_mode)
                print_fix_result(report.path, fixed=True, dry_run=False)
                files_fixed += 1

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    if total_unused == 0:
        print(green("✓ No unused imports found."))
    else:
        print(
            bold(f"Found {red(str(total_unused))} unused import(s) across {red(str(len(files_with_issues)))} file(s).")
        )
        if autofix and not dry_run:
            print(green(f"Fixed {files_fixed} file(s)."))

    return 0 if total_unused == 0 else 1


# ===========================================================================
# CLI
# ===========================================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unused_imports",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              %(prog)s src/
              %(prog)s src/ --autofix
              %(prog)s src/ --dry-run
              %(prog)s mypackage.whl
              %(prog)s . --exclude tests --workers 4 --verbose
              %(prog)s file.py --autofix --no-color
            """
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        metavar="PATH",
        help="Files or directories to scan (default: current directory).",
    )

    parser.add_argument(
        "-a",
        "--autofix",
        action="store_true",
        help="Remove unused imports in-place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files (implies --autofix mode).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Detailed output with per-name breakdown and progress.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        metavar="N",
        help="Number of parallel worker processes (default: 8).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Regex pattern to exclude files/dirs (repeatable).",
    )
    parser.add_argument(
        "--ignore-init",
        action="store_true",
        help="Treat all imports in __init__.py as used.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    import textwrap  # noqa: PLC0415  (local import to avoid top-level cost)

    parser = build_parser()
    args = parser.parse_args(argv)

    # Apply colour preference globally before any output
    global _USE_COLOR
    if args.no_color or not sys.stdout.isatty():
        _USE_COLOR = False

    # Compile exclude patterns up-front so bad regexes fail early
    exclude_patterns: list[re.Pattern[str]] = []
    for pat in args.exclude:
        try:
            exclude_patterns.append(re.compile(pat))
        except re.error as exc:
            print(red(f"error: invalid --exclude pattern {pat!r}: {exc}"), file=sys.stderr)
            return 2

    paths = [Path(p) for p in args.paths]

    return run(
        paths,
        autofix=args.autofix,
        dry_run=args.dry_run,
        verbose=args.verbose,
        workers=args.workers,
        exclude_patterns=exclude_patterns,
        ignore_init=args.ignore_init,
    )


if __name__ == "__main__":
    import textwrap

    sys.exit(main())
