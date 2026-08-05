#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

from pathlib import Path

import tree_sitter_cpp as tscpp
from dh import cprint
from tree_sitter import Language, Node, Parser

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def remove_blank_lines(text: str | Path) -> str:
    content = text
    if isinstance(text, Path):
        content = text.read_text(encoding="utf-8")

    if not isinstance(text, (str, Path)):
        return str(text)

    if isinstance(text, str) and Path(text).exists():
        content = Path(text).read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    result_lines = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result_lines.append(line)
        prev_blank = is_blank
    return "".join(result_lines)


class TSCppRemover:
    def __init__(self) -> None:
        self.parser = Parser()
        self.parser.language = Language(tscpp.language())

    def remove_comments(self, source: str) -> str:
        tree = self.parser.parse(source.encode("utf-8"))
        root = tree.root_node
        to_delete = []

        def walk(node: Node) -> None:
            if node.type == "comment":
                to_delete.append((node.start_byte, node.end_byte))
            for child in node.children:
                walk(child)

        walk(root)
        new_source = source.encode("utf-8")
        for start, end in sorted(to_delete, reverse=True):
            new_source = new_source[:start] + new_source[end:]
        cleaned = new_source.decode("utf-8")
        return remove_blank_lines(cleaned)


def process_file(path: Path) -> None:
    path = Path(path)
    before = path.stat().st_size
    remover = TSCppRemover()
    code = path.read_text(encoding="utf-8", errors="ignore")
    result = remover.remove_comments(code)
    if len(result) != len(code):
        path.write_text(result, encoding="utf-8")
        after = path.stat().st_size
        reduced = round((before - after) / before / 100, 3)
        cprint(f"[OK] {path.name} - {reduced} ", "cyan")
    else:
        cprint(f"[NO CHANGE] {path.name}", "blue")


if __name__ == "__main__":
    exts = {".cpp", ".cc", ".cxx", ".hpp", ".h", ".hh", ".hxx", ".c"}
    for path in Path().rglob("*"):
        if path.is_file() and path.suffix in exts:
            process_file(path)
