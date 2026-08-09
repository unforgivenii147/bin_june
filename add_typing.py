#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

from typing import Dict, List, Optional, Tuple


class TypingCollector(cst.CSTVisitor):
    def __init__(self):

        self.stack: List[Tuple[str, ...]] = []

        self.annotations: Dict[
            Tuple[str, ...],
            Tuple[cst.Parameters, Optional[cst.Annotation]],
        ] = {}

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        self.stack.append(node.name.value)

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        self.stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        self.stack.append(node.name.value)
        self.annotations[tuple(self.stack)] = (node.params, node.returns)
        return False

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.stack.pop()


class TypingTransformer(cst.CSTTransformer):
    def __init__(self, annotations):

        self.stack: List[Tuple[str, ...]] = []

        self.annotations: Dict[
            Tuple[str, ...],
            Tuple[cst.Parameters, Optional[cst.Annotation]],
        ] = annotations

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        self.stack.append(node.name.value)

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.CSTNode:
        self.stack.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        self.stack.append(node.name.value)
        return False

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.CSTNode:
        key = tuple(self.stack)
        self.stack.pop()
        if key in self.annotations:
            annotations = self.annotations[key]
            return updated_node.with_changes(params=annotations[0], returns=annotations[1])
        return updated_node


visitor = TypingCollector()
stub_tree.visit(visitor)
transformer = TypingTransformer(visitor.annotations)
modified_tree = source_tree.visit(transformer)
print(modified_tree.code)
import difflib

print("".join(difflib.unified_diff(py_source.splitlines(1), modified_tree.code.splitlines(1))))
if not modified_tree.deep_equals(source_tree):
    ...
