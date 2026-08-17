#!/data/data/com.termux/files/home/.local/bin/python
"""
Remove comments from bash scripts in place using tree-sitter.
Requirements:
    - Python 3.12+
    - tree-sitter==0.26.0
    - tree-sitter-bash  (the bash grammar; the proper companion for tree-sitter 0.26.0)
Features:
    * Detects bash scripts by `.sh`/`.bash` extension OR by shebang
      (so extensionless scripts like `~/bin/mytool` work too).
    * Removes full-line AND inline comments.
    * Preserves shebang (`
    * Uses `pathlib` and `concurrent.futures.ProcessPoolExecutor`.
    * Accepts multiple files/dirs; falls back to recursive current-dir scan.
    * Updates files in place.
    * Prints per-file stats using a relative path.
"""
from __future__ import annotations
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import tree_sitter_bash
from tree_sitter import Language, Node, Parser
BASH_LANGUAGE: Language = Language(tree_sitter_bash.language())
PARSER: Parser = Parser(BASH_LANGUAGE)
SHEBANG_PREFIXES: tuple[bytes, ...] = (
    b"#!/bin/bash",
    b"#!/bin/sh",
    b"#!/usr/bin/env bash",
    b"#!/usr/bin/env sh",
    b"#!/bin/env bash",
    b"#!/bin/env sh",
    b"#!/usr/bin/env zsh",
    b"#!/bin/zsh",
)
def is_bash_file(path: Path) -> bool:
    if path.suffix.lower() in (".sh", ".bash"):
        return True
    try:
        with path.open("rb") as fh:
            first_line = fh.readline()
    except OSError:
        return False
    return any(first_line.startswith(p) for p in SHEBANG_PREFIXES)
def find_comment_ranges(source: bytes) -> list[tuple[int, int, bool]]:
    tree = PARSER.parse(source)
    out: list[tuple[int, int, bool]] = []
    def walk(node: Node) -> None:
        if node.type == "comment":
            start, end = node.start_byte, node.end_byte
            if not (start == 0 and source.startswith(b"#!")):
                line_start = source.rfind(b"\n", 0, start) + 1
                prefix = source[line_start:start]
                is_inline = bool(prefix.strip())
                out.append((start, end, is_inline))
        for child in node.children:
            walk(child)
    walk(tree.root_node)
    out.sort(key=lambda r: r[0])
    return out
def strip_comments(source: bytes) -> tuple[bytes, int]:
    ranges = find_comment_ranges(source)
    if not ranges:
        return source, 0
    out = bytearray()
    last = 0
    for start, end, is_inline in ranges:
        out.extend(source[last:start])
        if is_inline:
            while out and out[-1:] in (b" ", b"\t"):
                out.pop()
        last = end
    out.extend(source[last:])
    return bytes(out), len(ranges)
def process_file(path: Path) -> tuple[str, int, str]:
    rel = os.path.relpath(path)
    try:
        source = path.read_bytes()
    except OSError as e:
        return rel, 0, f"read error: {e}"
    new_source, count = strip_comments(source)
    if count == 0:
        return rel, 0, ""
    try:
        path.write_bytes(new_source)
    except OSError as e:
        return rel, 0, f"write error: {e}"
    return rel, count, ""
def iter_targets(targets: list[Path]):
    seen: set[Path] = set()
    for target in targets:
        try:
            target = target.resolve()
        except OSError:
            continue
        if target.is_file():
            if is_bash_file(target) and target not in seen:
                seen.add(target)
                yield target
        elif target.is_dir():
            for p in sorted(target.rglob("*")):
                if p.is_file() and is_bash_file(p) and p not in seen:
                    seen.add(p)
                    yield p
        else:
            print(f"warning: {target} is not a file or directory", file=sys.stderr)
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Remove comments from bash scripts in place (tree-sitter powered).",
    )
    ap.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or directories to process. Defaults to the current directory (recursive).",
    )
    ap.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=max(1, os.cpu_count() or 1),
        help="Number of parallel worker processes (default: CPU count).",
    )
    args = ap.parse_args()
    targets: list[Path] = args.paths or [Path.cwd()]
    files = list(iter_targets(targets))
    if not files:
        print("no bash scripts found", file=sys.stderr)
        return 1
    total_removed = 0
    files_touched = 0
    errors = 0
    with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        futures = {ex.submit(process_file, f): f for f in files}
        for fut in as_completed(futures):
            rel, count, err = fut.result()
            if err:
                errors += 1
                print(f"{rel}: {err}", file=sys.stderr)
                continue
            if count:
                files_touched += 1
            total_removed += count
            print(f"{rel}: {count} comment(s) removed")
    print(
        f"\nDone: {files_touched}/{len(files)} file(s) modified, {total_removed} comment(s) removed, {errors} error(s)."
    )
    return 0 if errors == 0 else 2
if __name__ == "__main__":
    sys.exit(main())
