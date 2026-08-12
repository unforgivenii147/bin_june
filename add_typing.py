#!/data/data/com.termux/files/home/.local/bin/python
"""
Apply type annotations from .pyi stub files to source .py files using libcst.
Automatically finds .pyi file in same directory and updates .py in-place.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import libcst as cst


class TypingCollector(cst.CSTVisitor):
    """Extract type annotations from stub file."""

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
    """Apply type annotations from stub to source file."""

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
    """
    Validate that code is syntactically correct.

    Args:
        code: Python source code to validate
        filename: Filename for error reporting

    Returns:
        True if valid, False otherwise
    """
    try:
        cst.parse_module(code)
        return True
    except cst.ParserSyntaxError as e:
        print(
            f"✗ Syntax validation failed for {filename}: {e}",
            file=sys.stderr,
        )
        return False


def apply_stub_annotations(source_path: Path, show_diff: bool = True) -> bool:
    """
    Apply type annotations from .pyi to .py file (in-place).

    Args:
        source_path: Path to .py source file
        show_diff: Whether to display unified diff

    Returns:
        True if changes were applied, False otherwise
    """
    # Derive stub path
    stub_path = source_path.with_suffix(".pyi")

    try:
        # Validate paths exist
        if not source_path.exists():
            print(f"✗ Source file not found: {source_path}", file=sys.stderr)
            return False

        if not stub_path.exists():
            print(f"✗ Stub file not found: {stub_path}", file=sys.stderr)
            return False

        # Parse stub file
        stub_code = stub_path.read_text(encoding="utf-8")
        stub_tree = cst.parse_module(stub_code)

        # Parse source file
        source_code = source_path.read_text(encoding="utf-8")
        source_tree = cst.parse_module(source_code)

        # Extract annotations from stub
        collector = TypingCollector()
        stub_tree.visit(collector)
        print(
            f"✓ Collected {len(collector.annotations)} type annotations from {stub_path.name}",
            file=sys.stderr,
        )

        # Apply annotations to source
        transformer = TypingTransformer(collector.annotations)
        modified_tree = source_tree.visit(transformer)
        modified_code = modified_tree.code

        print(
            f"✓ Applied {transformer.applied} annotations to source",
            file=sys.stderr,
        )

        # Check if changes were made
        if modified_tree.deep_equals(source_tree):
            print("ℹ No changes required", file=sys.stderr)
            return False

        # Display diff
        if show_diff:
            diff_lines = list(
                difflib.unified_diff(
                    source_code.splitlines(keepends=True),
                    modified_code.splitlines(keepends=True),
                    fromfile=source_path.name,
                    tofile=f"{source_path.name} (annotated)",
                    n=2,
                )
            )
            if diff_lines:
                print("".join(diff_lines), end="")

        # Validate syntax before writing
        if not validate_syntax(modified_code, source_path.name):
            print(
                "✗ Validation failed: refusing to write invalid code",
                file=sys.stderr,
            )
            return False

        # Write changes in-place
        source_path.write_text(modified_code, encoding="utf-8")
        print(f"✓ Updated {source_path.name} in-place", file=sys.stderr)
        return True

    except cst.ParserSyntaxError as e:
        print(f"✗ Syntax error in input file: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Apply type annotations from .pyi stub to .py source file (in-place)",
        epilog="Stub file (.pyi) must be in the same directory as the source file.",
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Path to .py source file",
    )
    parser.add_argument(
        "--no-diff",
        action="store_true",
        help="Don't show unified diff",
    )

    args = parser.parse_args()

    success = apply_stub_annotations(
        source_path=args.source,
        show_diff=not args.no_diff,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
