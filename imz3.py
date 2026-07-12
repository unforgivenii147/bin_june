#!/data/data/com.termux/files/usr/bin/env python


import ast
from os import scandir as os_scandir
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
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
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def extract_imports_from_py(code: str, base_path: Path | None = None) -> set[str]:
    results = set()
    try:
        tree = ast.parse(code)
    except Exception:
        return results
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mod = a.name.split(".", 1)[0]
                if mod not in STDLIB:
                    results.add(mod)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                if base_path is not None:
                    module_str = "." * node.level
                    if node.module:
                        module_str += node.module
                    if is_local_module(base_path, module_str):
                        continue
                if node.module:
                    continue
                continue
            if node.module:
                mod = node.module.split(".", 1)[0]
                if mod not in STDLIB:
                    results.add(mod)
    return results


def is_local_module(base_path: Path, module: str) -> bool:
    dots = len(module) - len(module.lstrip("."))
    mod = module.lstrip(".")
    parent = base_path.parent
    for _ in range(dots - 1):
        parent = parent.parent
    pkg_dir = parent / mod.replace(".", "/")
    if (pkg_dir / "__init__.py").exists():
        return True
    py_file = pkg_dir.with_suffix(".py")
    return bool(py_file.exists())


def main() -> None:
    cwd = Path.cwd()
    importz = []
    for file in get_files(cwd, ext=[".py"]):
        with Path(file).open(encoding="utf-8") as f:
            contents = f.read()
            importz.append(extract_imports_from_py(contents))
    with Path("importz.txt").open("w", encoding="utf-8") as fo:
        for im in importz:
            fo.writelines(str(k) + "\n" for k in im)


if __name__ == "__main__":
    main()
