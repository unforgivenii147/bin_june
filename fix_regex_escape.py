#!/data/data/com.termux/files/usr/bin/env python

import ast
from ast import Call
from os import scandir as os_scandir
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def is_python_file(path: str | Path) -> bool:
    from ast import parse as ast_parse

    path = Path(path)
    if is_binary(path):
        return False
    if not path.stat().st_size:
        return False
    if path.is_file() and path.suffix == ".py":
        return True
    if not path.suffix:
        content = path.read_text(encoding="utf-8")
        if not content:
            return False
        if content.startswith("#!") and "python" in content[:100]:
            return True
        try:
            _ = ast_parse(content)
            return True
        except:
            return False
    return False


def is_binary(path: Path | str) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > 0.3
    except Exception:
        return True


def get_pyfiles(path: str | Path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        if path.suffix == ".py":
            return [path]
        if not path.suffix and not path.name.startswith(".") and is_python_file(path):
            return [path]
        return []

    if not path.is_dir():
        return []

    pyfiles = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        p = Path(entry.path)
                        if p.suffix == ".py":
                            pyfiles.append(p)
                        elif not p.suffix and not p.name.startswith(".") and is_python_file(p):
                            pyfiles.append(p)
        except (PermissionError, OSError):
            continue

    return sorted(pyfiles)


TARGET_FUNCS = {
    "compile",
    "search",
    "match",
    "fullmatch",
    "findall",
    "finditer",
    "split",
    "sub",
    "subn",
}


class RegexFixer(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> Call:
        self.generic_visit(node)
        if isinstance(node.func, ast.Attribute) and (
            isinstance(node.func.value, ast.Name)
            and node.func.value.id == "re"
            and node.func.attr in TARGET_FUNCS
            and node.args
        ):
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                original = first_arg.value
                fixed = original.encode("unicode_escape").decode("ascii")
                fixed = fixed.replace("\\\\n", "\\n")
                fixed = fixed.replace("\\\\t", "\\t")
                fixed = fixed.replace("\\\\r", "\\r")
                node.args[0] = ast.Constant(value=fixed)
                print(f"{original}\n{fixed}\n\n")
        return node


def fix_file(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        print(f"[SKIP] {path} (syntax error)")
        return False
    fixer = RegexFixer()
    new_tree = fixer.visit(tree)
    ast.fix_missing_locations(new_tree)
    new_source = ast.unparse(new_tree)
    if new_source != source:
        path.write_text(new_source, encoding="utf-8")
        print(f"[FIXED] {path}")
        return True
    return False


def main() -> None:
    cwd = Path()
    files = get_pyfiles(cwd)
    changed = 0
    for f in files:
        if fix_file(f):
            changed += 1
    print(f"\nDone. Modified {changed} files.")


if __name__ == "__main__":
    main()
