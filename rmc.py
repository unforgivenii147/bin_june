#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import argparse
import ast
import os
import sys
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Iterator

import tree_sitter_python as tsp
from tree_sitter import Language, Parser

PY_EXTS = {".py"}

_PARSER: Parser | None = None


def get_parser() -> Parser:
    global _PARSER

    if _PARSER is None:
        language = Language(tsp.language())
        _PARSER = Parser(language)

    return _PARSER


def line_start(content: bytes, offset: int) -> int:
    return content.rfind(b"\n", 0, offset) + 1


def line_end(content: bytes, offset: int) -> int:
    newline = content.find(b"\n", offset)
    return len(content) if newline == -1 else newline + 1


def node_line_start(content: bytes, node) -> int:
    return line_start(content, node.start_byte)


def node_line_end(content: bytes, node) -> int:
    return line_end(content, node.end_byte)


def is_keep_comment(comment: bytes, start_byte: int) -> bool:
    if start_byte == 0 and comment.startswith(b"#!"):
        return True

    stripped = comment.lstrip()
    if not stripped.startswith(b"#"):
        return False

    text = stripped[1:].lstrip().lower()

    if text.startswith((b"type:", b"fmt:")):
        return True

    if b"coding" in text and b":" in text:
        return True

    return False


def first_named_child(node):
    for child in node.children:
        if child.is_named:
            return child
    return None


def is_string_expression(node) -> bool:
    if node.type in {"string", "concatenated_string"}:
        return True

    if node.type != "expression_statement":
        return False

    child = first_named_child(node)
    return child is not None and child.type in {"string", "concatenated_string"}


def first_real_statement(container):
    for child in container.children:
        if child.is_named and child.type != "comment":
            return child
    return None


def is_docstring(node) -> bool:
    if not is_string_expression(node):
        return False

    parent = node.parent
    if parent is None:
        return False

    if parent.type == "module":
        return first_real_statement(parent) == node

    if parent.type != "block":
        return False

    owner = parent.parent
    if owner is None:
        return False

    if owner.type not in {
        "function_definition",
        "class_definition",
    }:
        return False

    return first_real_statement(parent) == node


def indent_for_block(block, content: bytes) -> bytes:
    for child in block.children:
        if not child.is_named:
            continue

        start = line_start(content, child.start_byte)
        indent = content[start : child.start_byte]

        if not indent.strip():
            return indent

    owner = block.parent
    if owner is not None:
        start = line_start(content, owner.start_byte)
        parent_indent = content[start : owner.start_byte]
        if not parent_indent.strip():
            return parent_indent + b"    "

    return b"    "


def block_named_children(block):
    for child in block.children:
        if child.is_named:
            yield child


def collect_actions(root, content: bytes) -> list[tuple[int, int, bytes]]:
    removals: dict[int, tuple[int, int, bytes]] = {}
    blocks: list = []

    stack = [root]

    while stack:
        node = stack.pop()

        if node.type == "comment":
            raw_comment = content[node.start_byte : node.end_byte]

            if not is_keep_comment(raw_comment, node.start_byte):
                start = node.start_byte
                end = node.end_byte

                before = content[line_start(content, start) : start]
                after = content[end : line_end(content, end)]

                if not before.strip() and not after.strip():
                    start = line_start(content, start)
                    end = line_end(content, end)

                removals[node.id] = (start, end, b"")

        elif is_docstring(node):
            start = node_line_start(content, node)
            end = node_line_end(content, node)
            removals[node.id] = (start, end, b"")

        if node.type == "block":
            blocks.append(node)

        children = node.children
        for child in reversed(children):
            stack.append(child)

    for block in blocks:
        first = None
        last = None
        all_removed = True

        for child in block_named_children(block):
            action = removals.get(child.id)

            if action is None:
                all_removed = False
                break

            if first is None:
                first = child

            last = child

        if not all_removed or first is None or last is None:
            continue

        first_action = removals[first.id]
        last_action = removals[last.id]

        replacement_start = line_start(content, first_action[0])
        replacement_end = last_action[1]

        indent = indent_for_block(block, content)
        removals[first.id] = (
            replacement_start,
            replacement_end,
            indent + b"pass\n",
        )

        for child in block_named_children(block):
            if child.id != first.id:
                removals.pop(child.id, None)

    actions = list(removals.values())
    actions.sort(key=lambda action: (action[0], action[1]))

    filtered: list[tuple[int, int, bytes]] = []
    previous_end = -1

    for action in actions:
        start, end, replacement = action

        if start < previous_end:
            continue

        filtered.append((start, end, replacement))
        previous_end = end

    return filtered


def apply_actions(content: bytes, actions: list[tuple[int, int, bytes]]) -> bytes:
    output = bytearray()
    last_end = 0

    for start, end, replacement in actions:
        output.extend(content[last_end:start])
        output.extend(replacement)
        last_end = end

    output.extend(content[last_end:])
    return bytes(output)


def strip_comments_and_docstrings(content: bytes) -> tuple[bytes, int]:
    parser = get_parser()
    tree = parser.parse(content)

    actions = collect_actions(tree.root_node, content)

    if not actions:
        return content, 0

    new_content = apply_actions(content, actions)

    try:
        ast.parse(new_content)
    except SyntaxError as exc:
        raise ValueError(f"Generated invalid Python source: {exc}") from exc

    return new_content, len(actions)


def process_file(path: Path, base: Path) -> tuple[str, int, str]:
    try:
        content = path.read_bytes()
        new_content, removed_count = strip_comments_and_docstrings(content)

        if new_content != content:
            path.write_bytes(new_content)

        try:
            relative_path = str(path.relative_to(base))
        except ValueError:
            relative_path = str(path)

        return relative_path, removed_count, ""

    except Exception as exc:
        return str(path), 0, str(exc)


def iter_py_files(paths: list[Path]) -> Iterator[Path]:
    seen: set[Path] = set()

    for path in paths:
        if path.is_file():
            if path.suffix.lower() not in PY_EXTS:
                continue

            resolved = path.resolve()

            if resolved not in seen:
                seen.add(resolved)
                yield path

            continue

        if not path.is_dir():
            continue

        try:
            for file_path in path.rglob("*.py"):
                if not file_path.is_file():
                    continue

                resolved = file_path.resolve()

                if resolved in seen:
                    continue

                seen.add(resolved)
                yield file_path

        except OSError as exc:
            print(f"{path}: ERROR walking directory: {exc}", file=sys.stderr)


def submit_until_full(
    executor: ProcessPoolExecutor,
    iterator: Iterator[Path],
    base: Path,
    pending: dict,
    max_pending: int,
) -> bool:
    exhausted = False

    while len(pending) < max_pending:
        try:
            path = next(iterator)
        except StopIteration:
            exhausted = True
            break

        future = executor.submit(process_file, path, base)
        pending[future] = path

    return exhausted


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove Python comments and docstrings in-place.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or directories. Defaults to the current directory recursively.",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=min(8, os.cpu_count() or 1),
        help="Number of worker processes (default: min(8, CPU count)).",
    )

    args = parser.parse_args()

    if args.jobs < 1:
        parser.error("--jobs must be at least 1")

    inputs = args.paths or [Path(".")]
    base = Path.cwd()

    file_iterator = iter_py_files(inputs)

    total_files = 0
    changed_files = 0
    total_removed = 0
    errors = 0

    max_pending = max(args.jobs * 4, args.jobs)

    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        pending: dict = {}
        exhausted = submit_until_full(
            executor,
            file_iterator,
            base,
            pending,
            max_pending,
        )

        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)

            for future in done:
                pending.pop(future, None)
                total_files += 1

                try:
                    relative_path, count, error = future.result()
                except Exception as exc:
                    errors += 1
                    print(f"Unknown file: ERROR: {exc}", file=sys.stderr)
                    continue

                if error:
                    errors += 1
                    print(f"{relative_path}: ERROR: {error}", file=sys.stderr)
                    continue

                total_removed += count

                if count:
                    changed_files += 1
                    print(f"{relative_path}: {count} comment(s)/docstring(s) removed")

            if not exhausted:
                exhausted = submit_until_full(
                    executor,
                    file_iterator,
                    base,
                    pending,
                    max_pending,
                )

    if total_files == 0:
        print("No Python files to process.", file=sys.stderr)
        return 1

    print(
        f"\nSummary: {changed_files}/{total_files} file(s) changed, "
        f"{total_removed} comment(s)/docstring(s) removed, "
        f"{errors} error(s)."
    )

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
