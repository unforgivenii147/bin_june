#!/data/data/com.termux/files/home/.local/bin/python
"""Remove comments from Python files using tree-sitter.

Processes files in place using parallel workers.
- Preserves shebangs (#!...), module docstrings, and pragmas (# type:, # fmt:).
- Removes function/class docstrings. If a docstring is the only node in a body,
  replaces it with 'pass' to prevent syntax errors.
- Validates result code with ast.parse() before writing to disk.
"""

import argparse
import ast
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import tree_sitter_python
from tree_sitter import Language, Parser

PY_EXTS = {".py"}


_PARSER: Parser | None = None


def get_parser() -> Parser:
    global _PARSER
    if _PARSER is None:
        lang = Language(tree_sitter_python.language())
        _PARSER = Parser(lang)
    return _PARSER


def is_docstring_node(node) -> bool:
    """Check if a node is an expression_statement containing a string."""
    if node.type != "expression_statement":
        return False
    if not node.children:
        return False
    return node.children[0].type in ("string", "concatenated_string")


def should_keep_comment(comment_bytes: bytes) -> bool:
    """Check if a comment should be preserved (type hints, fmt pragmas, encoding)."""
    stripped = comment_bytes.lstrip()
    if not stripped.startswith(b"#"):
        return False

    rest = stripped[1:].lstrip()
    if rest.lower().startswith((b"type:", b"fmt:")):
        return True

    # Preserve encoding declarations (e.g., # -*- coding: utf-8 -*-)
    if b"coding" in stripped.lower() and b":" in stripped:
        return True

    return False


def collect_actions(root, content: bytes):
    """Collect byte ranges to remove or replace. Returns dict {id(node): (start, end, replacement)}."""
    actions = {}
    blocks = []

    stack = [root]
    while stack:
        node = stack.pop()

        if node.type == "comment":
            if node.start_byte == 0 and content.startswith(b"#!"):
                pass
            elif should_keep_comment(content[node.start_byte : node.end_byte]):
                pass
            else:
                actions[id(node)] = (node.start_byte, node.end_byte, b"")

        elif node.type == "expression_statement" and is_docstring_node(node):
            parent = node.parent
            if parent:
                is_first = False
                for child in parent.children:
                    if child.is_named:
                        is_first = child.id == node.id
                        break

                if is_first:
                    if parent.type == "module":
                        pass
                    elif parent.type == "block":
                        grandparent = parent.parent
                        if grandparent and grandparent.type in ("function_definition", "class_definition"):
                            actions[id(node)] = (node.start_byte, node.end_byte, b"")

        elif node.type == "block":
            blocks.append(node)

        for child in reversed(node.children):
            stack.append(child)

    for block in blocks:
        named_children = [c for c in block.children if c.is_named]
        if named_children and all(id(c) in actions for c in named_children):
            first = named_children[0]
            s, e, _ = actions[id(first)]

            actions[id(first)] = (s, e, b"pass")

    return actions


def strip_comments(content: bytes) -> tuple[bytes, int]:
    """Remove comments/docstrings from `content`; return (new_bytes, removed_count)."""
    parser = get_parser()
    tree = parser.parse(content)
    actions = collect_actions(tree.root_node, content)

    if not actions:
        return content, 0

    sorted_actions = sorted(actions.values(), key=lambda x: x[0])

    out = bytearray()
    last = 0
    for start, end, repl in sorted_actions:
        out.extend(content[last:start])
        out.extend(repl)
        last = end
    out.extend(content[last:])

    new_content = bytes(out)

    try:
        ast.parse(new_content)
    except SyntaxError as e:
        raise ValueError(f"Generated invalid Python: {e}") from e

    return new_content, len(sorted_actions)


def process_file(path: Path, base: Path) -> tuple[str, int, str]:
    """Process one file in place. Returns (relpath, removed_count, error_str)."""
    try:
        content = path.read_bytes()
        new_content, count = strip_comments(content)
        if new_content != content:
            path.write_bytes(new_content)
        try:
            rel = str(path.relative_to(base))
        except ValueError:
            rel = str(path)
        return rel, count, ""
    except Exception as exc:
        return str(path), 0, str(exc)


def iter_py_files(paths: list[Path]):
    """Yield unique .py files from the given files/dirs (recursively for dirs)."""
    seen: set[Path] = set()
    for p in paths:
        if p.is_file() and p.suffix.lower() in PY_EXTS:
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                rp = f.resolve()
                if rp not in seen:
                    seen.add(rp)
                    yield f


def main() -> int:
    ap = argparse.ArgumentParser(description="Remove comments from Python files in place (tree-sitter powered).")
    ap.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or directories. Defaults to current directory recursively.",
    )
    ap.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=max(1, (os.cpu_count() or 2)),
        help="Number of parallel workers (default: CPU count).",
    )
    args = ap.parse_args()

    inputs = list(args.paths) if args.paths else [Path(".")]
    files = list(iter_py_files(inputs))
    if not files:
        print("No Python files to process.", file=sys.stderr)
        return 1

    base = Path.cwd()
    total_comments = 0
    files_changed = 0
    errors = 0

    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(process_file, p, base): p for p in files}
        for fut in as_completed(futs):
            rel, count, err = fut.result()
            if err:
                errors += 1
                print(f"{rel}: ERROR: {err}", file=sys.stderr)
                continue
            total_comments += count
            if count > 0:
                files_changed += 1
            print(f"{rel}: {count} comment(s) removed")

    print(
        f"\nSummary: {files_changed}/{len(files)} file(s) changed, "
        f"{total_comments} comment(s) removed, {errors} error(s)."
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
