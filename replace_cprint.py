#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import ast
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dh import get_pyfiles
CODE_BLOCK = r"""
def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files
"""
BLOCK_LINES = [line.rstrip() for line in CODE_BLOCK.strip("\n").splitlines()]
def find_block_range(lines: list[str]) -> tuple[int, int] | None:
    normalized = [line.rstrip("\n").rstrip() for line in lines]
    n, m = len(normalized), len(BLOCK_LINES)
    for i in range(n - m + 1):
        if normalized[i : i + m] == BLOCK_LINES:
            return (i, i + m)
    return None
def already_imports_get_files(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "dh":
            if any(alias.name == "get_files" for alias in node.names):
                return True
        if isinstance(node, ast.Import) and any(alias.name == "get_files" for alias in node.names):
            return True
    return False
def last_import_end_line(tree: ast.Module) -> int:
    last_end = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last_end = max(last_end, node.end_lineno)
        else:
            break
    return last_end
def process_file(path: Path):
    path = Path(path)
    if path.resolve() == Path(__file__).resolve():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"Skipping {path}: {e}")
        return
    lines = content.splitlines(keepends=True)
    match = find_block_range(lines)
    if match is None:
        return
    start, end = match
    # trim a single blank line immediately before/after the block, if present,
    # so we don't leave double blank lines behind
    if start > 0 and lines[start - 1].strip() == "":
        start -= 1
    if end < len(lines) and lines[end].strip() == "":
        end += 1
    del lines[start:end]
    new_content = "".join(lines)
    try:
        tree = ast.parse(new_content)
    except SyntaxError as e:
        print(f"Skipping write for {path} (would break syntax): {e}")
        return
    if already_imports_get_files(tree):
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            print(f"Removed block: {path} (get_files already imported)")
        return
    import_line = "from dh import get_files\n"
    body_lines = new_content.splitlines(keepends=True)
    last_end = last_import_end_line(tree)
    if last_end > 0:
        insert_idx = last_end
    else:
        insert_idx = 1 if body_lines and body_lines[0].startswith("#!") else 0
    body_lines.insert(insert_idx, import_line)
    final_content = "".join(body_lines)
    path.write_text(final_content, encoding="utf-8")
    print(f"Removed block and added import: {path}")
def main():
    cwd = Path.cwd()
    args = sys.argv[1:]
    py_files = [Path(p) for p in args] if args else get_pyfiles(cwd)
    with ThreadPoolExecutor(8) as executor:
        executor.map(process_file, py_files)
if __name__ == "__main__":
    main()
