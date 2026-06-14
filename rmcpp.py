#!/data/data/com.termux/files/usr/bin/python

import sys
from multiprocessing import get_context
from pathlib import Path

import tree_sitter_cpp as tscpp
from dh import get_files, remove_blank_lines
from tree_sitter import Language, Parser, Query, QueryCursor

ts_remover = None


class TSCppRemover:
    def __init__(self) -> None:
        self.language = Language(tscpp.language())
        self.parser = Parser(self.language)
        self.query = Query(self.language, "\n            (comment) @comment\n        ")

    def remove_comments(self, source: str) -> tuple[str, int]:
        source_bytes = source.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        cursor = QueryCursor(self.query)
        matches = cursor.matches(tree.root_node)
        deletions = []
        comment_count = 0
        for _pattern_idx, captures_dict in matches:
            for nodes in captures_dict.values():
                for node in nodes:
                    start = node.start_byte
                    end = node.end_byte
                    text = source_bytes[start:end].decode("utf-8")
                    stripped = text.strip()
                    if stripped.startswith(("//!", "///", "/**", "/*!", "///<", "//!<")):
                        continue
                    comment_count += 1
                    if end < len(source_bytes) and source_bytes[end: end + 1] == b"\n":
                        end += 1
                    deletions.append((start, end))
        deletions = sorted(set(deletions), reverse=True)
        new_source = bytearray(source_bytes)
        for start, end in deletions:
            del new_source[start:end]
        new_source = bytes(new_source)
        tree = self.parser.parse(new_source)
        if tree.root_node.has_error:
            print("Warning: Resulted code has syntax errors, returning original")
            return (source, 0)
        cleaned = new_source.decode("utf-8")
        cleaned = remove_blank_lines(cleaned)
        return (cleaned, comment_count)


def ts_remover_initializer() -> None:
    global ts_remover
    ts_remover = TSCppRemover()


def process_file(path):
    path = Path(path)
    global ts_remover
    try:
        code = path.read_text(encoding="utf-8")
        result, comments = ts_remover.remove_comments(code)
    except Exception as e:
        print(f"[ERROR] {path.name} processing: {e}")
        return ("error", path, 0)
    if comments:
        path.write_text(result, encoding="utf-8")
        print(f"[OK] {path.name}: {comments} comments removed")
        return ("changed", path, comments)
    print(f"[NO CHANGE] {path.name}")
    return ("nochange", path, 0)


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = (
        [Path(p) for p in args]
        if args
        else get_files(cwd, ext=[".js", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx", ".hh"])
    )
    before = gsz(cwd)
    with get_context("spawn").Pool(processes=8, initializer=ts_remover_initializer) as pool:
        results = pool.map(process_file, files)
    diffsize = before - gsz(cwd)
    changed = sum((1 for r in results if r[0] == "changed"))
    errors = [r for r in results if r[0] == "error"]
    nochg = sum((1 for r in results if r[0] == "nochange"))
    print(f"Files: {len(files)} | Changed: {changed} | Unchanged: {nochg} | Errors: {len(errors)}")
    if errors:
        print("\nErrors in:")
        for _, fn, *_ in errors:
            print(f"  - {fn}")
    print(f"Size reduced: {fsz(diffsize)}")
