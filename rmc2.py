#!/data/data/com.termux/files/home/.local/bin/python
"""
Remove Python comments and docstrings in-place without reformatting code.

Preserved:
- shebang lines
- comments containing "# fmt" or "# type"
- module docstrings by default

Examples:
    python rmc.py myfile.py
    python rmc.py ~/myprojects
    python rmc.py
    python rmc.py -r .
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable

from tree_sitter import Language, Parser
import tree_sitter_python as tspython


SKIP_DIRS = {".git", "__pycache__"}
PRESERVED_COMMENT_MARKERS = ("# fmt", "# type")


@dataclass(frozen=True)
class Edit:
    """A byte-range replacement edit."""

    start: int
    end: int
    replacement: bytes
    kind: str


@dataclass
class FileResult:
    path: str
    comments_removed: int = 0
    docstrings_removed: int = 0
    changed: bool = False
    error: str | None = None


def build_parser() -> Parser:
    """Create a Tree-sitter Python parser compatible with v0.26.0."""
    language = Language(tspython.language())
    parser = Parser(language)
    return parser


def iter_python_files(paths: Iterable[Path]) -> Generator[Path, None, None]:
    """
    Yield Python files from input paths.

    Does not descend into:
    - .git
    - __pycache__
    - symlinked directories

    Does not yield symlinked files.
    """
    seen: set[Path] = set()

    for input_path in paths:
        path = input_path.expanduser()

        try:
            if path.is_symlink():
                continue

            if path.is_file():
                if path.suffix == ".py":
                    resolved = path.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        yield path
                continue

            if not path.is_dir():
                print(f"warning: not found or unsupported: {path}", file=sys.stderr)
                continue

            for root_str, dirnames, filenames in os.walk(
                path,
                topdown=True,
                followlinks=False,
            ):
                root = Path(root_str)

                # Prune ignored and symlink directories before descent.
                dirnames[:] = [
                    dirname for dirname in dirnames if dirname not in SKIP_DIRS and not (root / dirname).is_symlink()
                ]

                for filename in filenames:
                    file_path = root / filename

                    if file_path.suffix != ".py":
                        continue

                    if file_path.is_symlink():
                        continue

                    try:
                        resolved = file_path.resolve()
                    except OSError:
                        continue

                    if resolved in seen:
                        continue

                    seen.add(resolved)
                    yield file_path

        except OSError as exc:
            print(f"warning: cannot traverse {path}: {exc}", file=sys.stderr)


def is_docstring_expr(node: ast.stmt) -> bool:
    """Return True if node is an expression statement containing a string."""
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def collect_docstring_nodes(tree: ast.AST, remove_module_docstring: bool) -> list[ast.Expr]:
    """
    Find docstring AST nodes.

    Includes docstrings in:
    - modules
    - functions and async functions
    - classes

    Module docstrings are retained unless -r/--remove-module-docstring is used.
    """
    result: list[ast.Expr] = []

    def visit_body_owner(node: ast.AST, is_module: bool = False) -> None:
        body = getattr(node, "body", None)

        if isinstance(body, list) and body and is_docstring_expr(body[0]):
            docstring = body[0]

            if not is_module or remove_module_docstring:
                result.append(docstring)

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit_body_owner(child)
            elif not isinstance(
                child,
                (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                visit_nested(child)

    def visit_nested(node: ast.AST) -> None:
        """
        Find nested definitions in nodes such as if/try/with blocks.

        A function/class can be defined inside arbitrary compound statements.
        """
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit_body_owner(child)
            else:
                visit_nested(child)

    visit_body_owner(tree, is_module=True)
    return result


def line_col_to_offset(source: str, line: int, col: int) -> int:
    """Convert a 1-based AST line and 0-based column to a character offset."""
    lines = source.splitlines(keepends=True)
    return sum(len(item) for item in lines[: line - 1]) + col


def ast_node_byte_range(source: str, node: ast.AST) -> tuple[int, int]:
    """
    Return UTF-8 byte range for an AST node.

    ast.get_source_segment() is intentionally used here to preserve the exact
    original literal spelling, including raw strings such as r'\\d+'.
    """
    segment = ast.get_source_segment(source, node)
    if segment is None:
        raise ValueError("could not obtain original source segment")

    start_char = line_col_to_offset(source, node.lineno, node.col_offset)
    start_byte = len(source[:start_char].encode("utf-8"))
    segment_bytes = segment.encode("utf-8")

    return start_byte, start_byte + len(segment_bytes)


def comment_should_be_preserved(comment: bytes, is_first_line: bool) -> bool:
    """Keep shebangs, # fmt directives, and # type comments."""
    stripped = comment.lstrip()

    if is_first_line and stripped.startswith(b"#!"):
        return True

    lower = comment.lower()
    return any(marker.encode() in lower for marker in PRESERVED_COMMENT_MARKERS)


def collect_comment_edits(source_bytes: bytes, parser: Parser) -> list[Edit]:
    """Collect removable comment nodes from Tree-sitter."""
    tree = parser.parse(source_bytes)
    edits: list[Edit] = []

    stack = [tree.root_node]

    while stack:
        node = stack.pop()

        if node.type == "comment":
            line_number = node.start_point.row + 1
            comment = source_bytes[node.start_byte : node.end_byte]

            if not comment_should_be_preserved(comment, line_number == 1):
                edits.append(
                    Edit(
                        start=node.start_byte,
                        end=node.end_byte,
                        replacement=b"",
                        kind="comment",
                    )
                )

        stack.extend(reversed(node.children))

    return edits


def is_only_body_statement(docstring: ast.Expr, source_tree: ast.AST) -> bool:
    """
    Return True if this docstring is the only statement in a function/class body.

    Module docstrings are deliberately excluded because a module may legally
    become empty.
    """
    for node in ast.walk(source_tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        if node.body and node.body[0] is docstring:
            return len(node.body) == 1

    return False


def indentation_before(source_bytes: bytes, byte_offset: int) -> bytes:
    """Get leading whitespace for the line containing byte_offset."""
    line_start = source_bytes.rfind(b"\n", 0, byte_offset) + 1
    prefix = source_bytes[line_start:byte_offset]

    whitespace = bytearray()
    for char in prefix:
        if char in (ord(" "), ord("\t")):
            whitespace.append(char)
        else:
            break

    return bytes(whitespace)


def collect_docstring_edits(
    source: str,
    source_bytes: bytes,
    source_tree: ast.AST,
    remove_module_docstring: bool,
) -> list[Edit]:
    """Create exact byte edits for removable docstrings."""
    edits: list[Edit] = []

    for docstring in collect_docstring_nodes(source_tree, remove_module_docstring):
        start, end = ast_node_byte_range(source, docstring)

        if is_only_body_statement(docstring, source_tree):
            indent = indentation_before(source_bytes, start)
            replacement = b"pass"
        else:
            replacement = b""

        edits.append(
            Edit(
                start=start,
                end=end,
                replacement=replacement,
                kind="docstring",
            )
        )

    return edits


def remove_empty_comment_lines(data: bytes) -> bytes:
    """
    Remove lines that became empty after a full-line comment was removed.

    This avoids leaving unnecessary blank lines for standalone comments while
    preserving line endings and normal code layout.
    """
    lines = data.splitlines(keepends=True)
    result: list[bytes] = []

    for line in lines:
        content = line.rstrip(b"\r\n")

        if content.strip(b" \t") == b"":
            continue

        result.append(line)

    return b"".join(result)


def apply_edits(source_bytes: bytes, edits: list[Edit]) -> bytes:
    """
    Apply edits from back to front.

    Overlapping edits are rejected because that would indicate an unexpected
    parser/AST source-range mismatch.
    """
    if not edits:
        return source_bytes

    ordered = sorted(edits, key=lambda edit: (edit.start, edit.end), reverse=True)

    previous_start = len(source_bytes) + 1
    output = source_bytes

    for edit in ordered:
        if edit.end > previous_start:
            raise ValueError(f"overlapping edit detected: {edit}")

        output = output[: edit.start] + edit.replacement + output[edit.end :]
        previous_start = edit.start

    return output


def process_file(path_str: str, remove_module_docstring: bool) -> FileResult:
    """Process one Python file. Intended to run in a worker process."""
    path = Path(path_str)
    result = FileResult(path=str(path))

    try:
        source_bytes = path.read_bytes()

        try:
            source = source_bytes.decode("utf-8")
        except UnicodeDecodeError:
            source = source_bytes.decode("utf-8-sig")

        source_tree = ast.parse(source, filename=str(path))

        parser = build_parser()
        comment_edits = collect_comment_edits(source_bytes, parser)
        docstring_edits = collect_docstring_edits(
            source,
            source_bytes,
            source_tree,
            remove_module_docstring,
        )

        edits = comment_edits + docstring_edits

        if not edits:
            return result

        updated = apply_edits(source_bytes, edits)

        # Validate before changing the actual file.
        updated_text = updated.decode("utf-8")
        ast.parse(updated_text, filename=str(path))

        if updated == source_bytes:
            return result

        path.write_bytes(updated)

        result.comments_removed = len(comment_edits)
        result.docstrings_removed = len(docstring_edits)
        result.changed = True
        return result

    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove Python comments and docstrings recursively, preserving "
            "shebangs, # fmt, # type, and module docstrings by default."
        )
    )
    parser.add_argument(
        "-r",
        "--remove-module-docstring",
        action="store_true",
        help="remove module-level docstrings too",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=max(1, os.cpu_count() or 1),
        help="number of worker processes (default: CPU count)",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="files and/or directories to process (default: current directory)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_paths = args.paths or [Path(".")]

    files = list(iter_python_files(input_paths))

    if not files:
        print("No Python files found.")
        return 0

    changed_files = 0
    total_comments = 0
    total_docstrings = 0
    errors = 0

    with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        futures = {
            executor.submit(
                process_file,
                str(path),
                args.remove_module_docstring,
            ): path
            for path in files
        }

        for future in as_completed(futures):
            result = future.result()

            if result.error:
                errors += 1
                print(f"ERROR {result.path}: {result.error}", file=sys.stderr)
                continue

            if result.changed:
                changed_files += 1
                total_comments += result.comments_removed
                total_docstrings += result.docstrings_removed

                print(
                    f"{result.path}: "
                    f"comments removed={result.comments_removed}, "
                    f"docstrings removed={result.docstrings_removed}"
                )
            else:
                print(f"{result.path}: no changes")

    print(
        "\nSummary: "
        f"files changed={changed_files}, "
        f"comments removed={total_comments}, "
        f"docstrings removed={total_docstrings}, "
        f"errors={errors}"
    )

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
