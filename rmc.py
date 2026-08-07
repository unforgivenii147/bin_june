#!/data/data/com.termux/files/home/.local/bin/python
"""rmc.py — Remove comments and docstrings from Python files using AST + tokenize.

Usage:
    python rmc.py                    # process . recursively
    python rmc.py myfile.py          # process one file
    python rmc.py ~/myprojects       # process dir recursively
    python rmc.py dir1 dir2 file.py  # multiple targets
    python rmc.py -r ...             # remove module-level docstrings too
"""

from __future__ import annotations

import argparse
import ast
import sys
import tokenize
import io
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKIP_DIRS = {".git", "__pycache__"}

# Comment prefixes/patterns to preserve (checked on stripped comment text)
PRESERVE_COMMENT_PREFIXES = (
    "#!",  # shebangs  (only on line 1, but we guard by prefix too)
    "# fmt",  # black fmt directives  e.g.  # fmt: off / # fmt: skip
    "# type",  # type: ignore / type: ...
    "# noqa",  # noqa directives (bonus — common to preserve)
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_docstring_node(node: ast.AST) -> bool:
    """Return True if *node* is an ast.Expr whose value is a string constant."""
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _should_preserve_comment(text: str) -> bool:
    """Return True if a comment token should be kept."""
    stripped = text.strip()
    # Shebang
    if stripped.startswith("#!"):
        return True
    for prefix in PRESERVE_COMMENT_PREFIXES:
        if stripped.lower().startswith(prefix.lower()):
            return True
    return False


# ---------------------------------------------------------------------------
# Core transformer
# ---------------------------------------------------------------------------


class _DocstringInfo:
    """Tracks which AST Expr-docstring nodes should be removed."""

    def __init__(self, source: str, tree: ast.Module, remove_module_doc: bool):
        self.source = source
        self.remove_module_doc = remove_module_doc
        # Set of (lineno, col_offset) for Expr nodes that are docstrings to remove
        self.to_remove: set[tuple[int, int]] = set()
        # Set of (lineno, col_offset) for Expr nodes that need a 'pass' replacement
        self.needs_pass: set[tuple[int, int]] = set()
        self._collect(tree)

    def _collect(self, tree: ast.Module) -> None:
        # Module-level docstring
        if self.remove_module_doc and tree.body and _is_docstring_node(tree.body[0]):
            node = tree.body[0]
            self.to_remove.add((node.lineno, node.col_offset))
            # Module body becoming empty is fine — no 'pass' needed at module level

        # Function / class / async-function docstrings
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if not node.body:
                continue
            first = node.body[0]
            if not _is_docstring_node(first):
                continue
            key = (first.lineno, first.col_offset)
            self.to_remove.add(key)
            # If docstring is the *only* statement, we must insert 'pass'
            if len(node.body) == 1:
                self.needs_pass.add(key)


def _collect_comment_ranges(
    source: str,
) -> list[tuple[int, int, int, int, bool]]:
    """
    Tokenize *source* and return a list of
        (start_row, start_col, end_row, end_col, preserve)
    for every COMMENT token.
    Rows are 1-based (as returned by tokenize).
    """
    results = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in tokens:
            if tok.type != tokenize.COMMENT:
                continue
            sr, sc = tok.start  # 1-based row, 0-based col
            er, ec = tok.end
            preserve = _should_preserve_comment(tok.string)
            results.append((sr, sc, er, ec, preserve))
    except tokenize.TokenError:
        pass
    return results


# ---------------------------------------------------------------------------
# Source rebuilder
# ---------------------------------------------------------------------------


def _lines_to_offsets(source: str) -> list[int]:
    """
    Return a list where index i holds the character offset of the start of
    line i+1 (1-based line numbers).  Line 0 sentinel = 0.
    """
    offsets = [0]  # offset[0] unused, line numbers are 1-based
    pos = 0
    for ch in source:
        pos += 1
        if ch == "\n":
            offsets.append(pos)
    return offsets


def _rowcol_to_offset(offsets: list[int], row: int, col: int) -> int:
    return offsets[row] + col


def process_source(source: str, remove_module_doc: bool) -> tuple[str, int, int]:
    """
    Process *source* and return (new_source, n_comments_removed, n_docstrings_removed).
    Raises ValueError if the result fails ast.parse validation.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"Source has syntax error: {exc}") from exc

    offsets = _lines_to_offsets(source)

    # ------------------------------------------------------------------ #
    # 1. Collect docstring byte-ranges to remove
    # ------------------------------------------------------------------ #
    doc_info = _DocstringInfo(source, tree, remove_module_doc)

    # Map (lineno, col_offset) -> ast.Expr node for easy lookup
    expr_nodes: dict[tuple[int, int], ast.Expr] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr):
            expr_nodes[(node.lineno, node.col_offset)] = node

    # Build list of (start_offset, end_offset, replacement) for docstrings
    # replacement is '' or 'pass\n' (indented appropriately)
    doc_removals: list[tuple[int, int, str]] = []
    n_doc = 0

    for key in doc_info.to_remove:
        expr_node = expr_nodes.get(key)
        if expr_node is None:
            continue
        # Use get_source_segment to find exact extent — but we need offsets.
        # ast stores end_lineno / end_col_offset on Python 3.8+
        if not hasattr(expr_node, "end_lineno"):
            continue

        start = _rowcol_to_offset(offsets, expr_node.lineno, expr_node.col_offset)
        end = _rowcol_to_offset(offsets, expr_node.end_lineno, expr_node.end_col_offset)

        # Consume the trailing newline(s) so we don't leave blank lines
        while end < len(source) and source[end] in ("\n", "\r"):
            end += 1

        replacement = ""
        if key in doc_info.needs_pass:
            indent = " " * expr_node.col_offset
            replacement = f"{indent}pass\n"

        doc_removals.append((start, end, replacement))
        n_doc += 1

    # ------------------------------------------------------------------ #
    # 2. Collect comment token ranges to remove
    # ------------------------------------------------------------------ #
    comment_tokens = _collect_comment_ranges(source)
    comment_removals: list[tuple[int, int, str]] = []
    n_comments = 0

    for sr, sc, er, ec, preserve in comment_tokens:
        if preserve:
            continue
        start = _rowcol_to_offset(offsets, sr, sc)
        end = _rowcol_to_offset(offsets, er, ec)

        # If the comment is the only non-whitespace on its line, remove the
        # whole line (including leading whitespace and trailing newline).
        line_start = offsets[sr]
        before_comment = source[line_start:start]
        is_whole_line = before_comment.strip() == ""

        if is_whole_line:
            # extend start back to beginning of line
            start = line_start
            # extend end to consume the newline
            if end < len(source) and source[end] == "\n":
                end += 1

        comment_removals.append((start, end, ""))
        n_comments += 1

    # ------------------------------------------------------------------ #
    # 3. Merge all removals, sort by start offset, rebuild source
    # ------------------------------------------------------------------ #
    all_removals = sorted(doc_removals + comment_removals, key=lambda x: x[0])

    # Remove overlapping ranges (keep first)
    merged: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, repl in all_removals:
        if start < last_end:
            continue  # overlaps with previous removal — skip
        merged.append((start, end, repl))
        last_end = end

    if not merged:
        return source, 0, 0

    parts: list[str] = []
    cursor = 0
    for start, end, repl in merged:
        parts.append(source[cursor:start])
        parts.append(repl)
        cursor = end
    parts.append(source[cursor:])

    new_source = "".join(parts)

    # ------------------------------------------------------------------ #
    # 4. Validate
    # ------------------------------------------------------------------ #
    try:
        ast.parse(new_source)
    except SyntaxError as exc:
        raise ValueError(f"Result failed ast.parse validation: {exc}") from exc

    return new_source, n_comments, n_doc


# ---------------------------------------------------------------------------
# File-level worker (runs in subprocess via ProcessPoolExecutor)
# ---------------------------------------------------------------------------


def process_file(path_str: str, remove_module_doc: bool) -> dict:
    """
    Worker function.  Returns a result dict suitable for reporting.
    Accepts str path so it is picklable across processes.
    """
    path = Path(path_str)
    result = {
        "path": path_str,
        "comments": 0,
        "docstrings": 0,
        "skipped": False,
        "skip_reason": "",
        "error": "",
    }
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as exc:
        result["error"] = f"read error: {exc}"
        return result

    try:
        new_source, n_comments, n_doc = process_source(source, remove_module_doc)
    except ValueError as exc:
        result["error"] = str(exc)
        return result

    total = n_comments + n_doc
    if total == 0:
        result["skipped"] = True
        result["skip_reason"] = "nothing to remove"
        return result

    try:
        path.write_text(new_source, encoding="utf-8")
    except Exception as exc:
        result["error"] = f"write error: {exc}"
        return result

    result["comments"] = n_comments
    result["docstrings"] = n_doc
    return result


# ---------------------------------------------------------------------------
# Filesystem walker (generator)
# ---------------------------------------------------------------------------


def walk_python_files(root: Path):
    """Yield .py files under *root*, skipping SKIP_DIRS and symlinks."""
    if root.is_symlink():
        return
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    # Use a stack for iterative DFS — avoids deep recursion on large trees
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except PermissionError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in SKIP_DIRS:
                    stack.append(entry)
            elif entry.is_file() and entry.suffix == ".py":
                yield entry


def collect_targets(inputs: list[str]) -> list[Path]:
    """Resolve CLI inputs to a deduplicated list of Path targets."""
    if not inputs:
        return [Path(".")]
    return [Path(p).expanduser().resolve() for p in inputs]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
BOLD = "\033[1m"


def _fmt(color: str, text: str) -> str:
    return f"{color}{text}{RESET}" if sys.stdout.isatty() else text


def report_result(res: dict) -> None:
    path = res["path"]
    if res["error"]:
        print(f"  {_fmt(RED, 'ERROR')} {path}: {res['error']}")
    elif res["skipped"]:
        pass  # silent for unchanged files
    else:
        c = res["comments"]
        d = res["docstrings"]
        parts = []
        if c:
            parts.append(f"{c} comment{'s' if c != 1 else ''}")
        if d:
            parts.append(f"{d} docstring{'s' if d != 1 else ''}")
        print(f"  {_fmt(GREEN, 'cleaned')} {path}: removed {', '.join(parts)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rmc",
        description="Remove comments and docstrings from Python files.",
    )
    p.add_argument(
        "targets",
        nargs="*",
        metavar="PATH",
        help="Files or directories to process (default: current directory).",
    )
    p.add_argument(
        "-r",
        "--remove-module-docstrings",
        action="store_true",
        default=False,
        help="Also remove module-level docstrings (preserved by default).",
    )
    p.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        metavar="N",
        help="Number of parallel worker processes (default: cpu count).",
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    targets = collect_targets(args.targets)
    remove_module_doc: bool = args.remove_module_docstrings

    # Collect all .py files via generator
    all_files: list[Path] = []
    for target in targets:
        if not target.exists():
            print(f"{_fmt(RED, 'warning')}: path not found: {target}", file=sys.stderr)
            continue
        for f in walk_python_files(target):
            all_files.append(f)

    # Deduplicate (in case overlapping dirs were given)
    seen: set[Path] = set()
    unique_files: list[Path] = []
    for f in all_files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)

    if not unique_files:
        print("No Python files found.")
        return 0

    print(
        f"{_fmt(BOLD, 'rmc')} — processing "
        f"{_fmt(CYAN, str(len(unique_files)))} file(s)" + (" [removing module docstrings]" if remove_module_doc else "")
    )

    total_comments = 0
    total_docstrings = 0
    total_errors = 0
    total_cleaned = 0

    # Use ProcessPoolExecutor for parallel processing
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(process_file, str(f), remove_module_doc): f for f in unique_files}
        for future in as_completed(futures):
            try:
                res = future.result()
            except Exception as exc:
                path = str(futures[future])
                print(f"  {_fmt(RED, 'ERROR')} {path}: unexpected: {exc}")
                total_errors += 1
                continue

            report_result(res)
            if res["error"]:
                total_errors += 1
            elif not res["skipped"]:
                total_cleaned += 1
                total_comments += res["comments"]
                total_docstrings += res["docstrings"]

    print(
        f"\n{_fmt(BOLD, 'done')} — "
        f"{total_cleaned} file(s) cleaned, "
        f"{total_comments} comment(s) removed, "
        f"{total_docstrings} docstring(s) removed"
        + (f", {_fmt(RED, str(total_errors) + ' error(s)')}" if total_errors else "")
    )
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
