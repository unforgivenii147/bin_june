#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import ast
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import libcst as cst
from libcst import EmptyLine, Pass, SimpleStatementLine
from libcst.metadata import MetadataWrapper, PositionProvider

ROOT = Path(".").resolve()


class StripTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        self.comments_removed = 0
        self.docstrings_removed = 0

    @staticmethod
    def _is_docstring_statement(stmt: cst.BaseStatement) -> bool:
        if not isinstance(stmt, cst.SimpleStatementLine):
            return False
        if len(stmt.body) != 1:
            return False
        expr = stmt.body[0]
        if not isinstance(expr, cst.Expr):
            return False
        return isinstance(expr.value, cst.SimpleString)

    @staticmethod
    def _is_preserved_comment(value: str) -> bool:
        stripped = value.lstrip()

        return stripped.startswith(("#!", "# fmt", "# type"))

    def leave_Comment(
        self,
        original_node: cst.Comment,
        updated_node: cst.Comment,
    ) -> cst.Comment | cst.RemovalSentinel:
        if self._is_preserved_comment(original_node.value):
            return updated_node

        self.comments_removed += 1
        return cst.RemoveFromParent()

    def leave_EmptyLine(
        self,
        original_node: EmptyLine,
        updated_node: EmptyLine,
    ) -> EmptyLine:
        if updated_node.comment is None:
            return updated_node

        comment = updated_node.comment
        if self._is_preserved_comment(comment.value):
            return updated_node

        self.comments_removed += 1
        return updated_node.with_changes(comment=None)

    def leave_Module(
        self,
        original_node: cst.Module,
        updated_node: cst.Module,
    ) -> cst.Module:
        body = list(updated_node.body)

        start = 1 if body and self._is_docstring_statement(body[0]) else 0

        new_body = body[:start]

        for stmt in body[start:]:
            if self._is_docstring_statement(stmt):
                self.docstrings_removed += 1
            else:
                new_body.append(stmt)

        return updated_node.with_changes(body=new_body)

    def _strip_suite(
        self,
        body: tuple[cst.BaseStatement, ...],
    ) -> tuple[cst.BaseStatement, ...]:
        statements = list(body)

        if statements and self._is_docstring_statement(statements[0]):
            self.docstrings_removed += 1
            statements = statements[1:]

        if not statements:
            statements = [SimpleStatementLine(body=[Pass()])]

        return tuple(statements)

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef,
    ) -> cst.FunctionDef:
        body = updated_node.body

        if isinstance(body, cst.IndentedBlock):
            return updated_node.with_changes(
                body=body.with_changes(
                    body=self._strip_suite(body.body),
                )
            )

        return updated_node

    def leave_ClassDef(
        self,
        original_node: cst.ClassDef,
        updated_node: cst.ClassDef,
    ) -> cst.ClassDef:
        body = updated_node.body

        if isinstance(body, cst.IndentedBlock):
            return updated_node.with_changes(body=body.with_changes(body=self._strip_suite(body.body)))

        return updated_node


def process_file(path: Path) -> None:
    path = path.resolve()
    source = path.read_text(encoding="utf-8")

    try:
        module = cst.parse_module(source)
    except Exception as exc:
        print(f"SKIP {path}: parse failed: {exc}")
        return

    wrapper = MetadataWrapper(module)
    transformer = StripTransformer()

    try:
        updated = wrapper.visit(transformer)
    except Exception as exc:
        print(f"SKIP {path}: transform failed: {exc}")
        return

    code = updated.code

    try:
        ast.parse(code)
    except SyntaxError as exc:
        print(f"ERROR {path}: transformed code is invalid: {exc}")
        return

    if code != source:
        path.write_text(code, encoding="utf-8")

    rel = os.path.relpath(path, ROOT)
    print(f"{rel}: comments={transformer.comments_removed}, docstrings={transformer.docstrings_removed}")


def main() -> None:
    paths = sorted(ROOT.rglob("*.py"))

    workers = os.cpu_count() or 1

    with ProcessPoolExecutor(max_workers=workers) as executor:
        list(executor.map(process_file, paths))


if __name__ == "__main__":
    main()
