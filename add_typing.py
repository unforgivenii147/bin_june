#!/data/data/com.termux/files/home/.local/bin/python
"""
Apply type annotations from .pyi stub files to source .py files using libcst.
Automatically finds .pyi file in same directory and updates .py in-place.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path
from typing import Dict, Optional

import libcst as cst
from dh import get_files, mpf3


class TypingCollector(cst.CSTVisitor):
    def __init__(self):
        self.stack: list[tuple[str, ...]] = []
        self.annotations: Dict[
            tuple[str, ...],
            tuple[cst.Parameters, Optional[cst.Annotation]],
        ] = {}

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        self.stack.append(node.name.value)
        return True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        self.stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        self.stack.append(node.name.value)
        self.annotations[tuple(self.stack)] = (node.params, node.returns)
        return False

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.stack.pop()


class TypingTransformer(cst.CSTTransformer):
    def __init__(
        self,
        annotations: Dict[
            tuple[str, ...],
            tuple[cst.Parameters, Optional[cst.Annotation]],
        ],
    ):
        self.stack: list[tuple[str, ...]] = []
        self.annotations = annotations
        self.applied = 0

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        self.stack.append(node.name.value)
        return True

    def leave_ClassDef(
        self,
        original_node: cst.ClassDef,
        updated_node: cst.ClassDef,
    ) -> cst.CSTNode:
        self.stack.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        self.stack.append(node.name.value)
        return False

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef,
    ) -> cst.CSTNode:
        key = tuple(self.stack)
        self.stack.pop()
        if key in self.annotations:
            params, returns = self.annotations[key]
            updated_node = updated_node.with_changes(
                params=params,
                returns=returns,
            )
            self.applied += 1
        return updated_node


def validate_syntax(code: str, filename: str) -> bool:
    try:
        cst.parse_module(code)
        return True
    except cst.ParserSyntaxError as e:
        print(
            f"✗ Syntax validation failed for {filename}: {e}",
            file=sys.stderr,
        )
        return False


def process_file(path: Path):
    path = Path(path)
    stub_path = path.with_suffix(".pyi")
    try:
        if not path.exists():
            print(f"✗ Source file not found: {path}", file=sys.stderr)
            return
        if not stub_path.exists():
            print(f"✗ Stub file not found: {stub_path}", file=sys.stderr)
            return
        print(f"processing ... {path.name}")
        stub_code = stub_path.read_text(encoding="utf-8")
        stub_tree = cst.parse_module(stub_code)
        source_code = path.read_text(encoding="utf-8")
        source_tree = cst.parse_module(source_code)
        collector = TypingCollector()
        stub_tree.visit(collector)
        print(
            f"✓ Collected {len(collector.annotations)} type annotations from {stub_path.name}",
            file=sys.stderr,
        )
        transformer = TypingTransformer(collector.annotations)
        modified_tree = source_tree.visit(transformer)
        modified_code = modified_tree.code
        print(
            f"✓ Applied {transformer.applied} annotations to source",
            file=sys.stderr,
        )
        if modified_tree.deep_equals(source_tree):
            print("ℹ No changes required", file=sys.stderr)
            return False
        diff_lines = list(
            difflib.unified_diff(
                source_code.splitlines(keepends=True),
                modified_code.splitlines(keepends=True),
                fromfile=path.name,
                tofile=f"{path.name} (annotated)",
                n=2,
            )
        )
        if diff_lines:
            print("".join(diff_lines), end="")
        if not validate_syntax(modified_code, path.name):
            print(
                "✗ Validation failed: refusing to write invalid code",
                file=sys.stderr,
            )
            return
        path.write_text(modified_code, encoding="utf-8")
        print(f"✓ Updated {path.name} in-place", file=sys.stderr)
        return
    except cst.ParserSyntaxError as e:
        print(f"✗ Syntax error in input file: {e}", file=sys.stderr)
        return
    except Exception as e:
        print(f"✗ Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return


def main():
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".py"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(0)
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
