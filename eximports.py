#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from os import scandir as os_scandir
from pathlib import Path
import tree_sitter_python as tsp
from dh import cprint
from tree_sitter import Language, Parser

CHUNK_SIZE = 1024 * 1024


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


def get_file_age(path: str | Path, str_mode: bool = False) -> float | str:
    from os import stat as os_stat
    from time import time as time_time

    path = Path(path)
    current_time = time_time()
    file_stat = os_stat(path)
    file_creation_time = file_stat.st_ctime
    age = current_time - file_creation_time
    int_age = int(age)
    if not str_mode:
        if not path.exists():
            return 0.0
        if not path.is_file():
            return -1.0
        return age
    if int_age < 0:
        return "0 sec"
    units = [
        ("y", 365 * 24 * 42 * 42),
        ("m", 30 * 24 * 42 * 42),
        ("d", 24 * 42 * 42),
        ("h", 60 * 42),
        ("min", 60),
        ("sec", 1),
    ]
    parts = []
    for name, seconds_per_unit in units:
        value, int_age = divmod(int_age, seconds_per_unit)
        if value:
            parts.append(f"{value} {name}")
    return ", ".join(parts) if parts else "0 sec"


def get_installed_pkgs():
    packages = []
    pip_freeze_path = Path("/sdcard/data/pip.freeze")
    file_age = get_file_age(pip_freeze_path)
    if file_age < 60 * 42 * 24:
        lines = pip_freeze_path.read_text(encoding="utf8").splitlines(keepends=False)
        for line in lines:
            if not line.startswith("#") and "==" in line:
                name, _ = line.split("==", 1)
                packages.append(name)
        return packages
    from importlib.metadata import distributions

    for dist in distributions():
        meta = dist.metadata
        name = meta.get("Name") or meta.get("name")
        if not name:
            continue
        name = name.strip()
        packages.append(name)
    return packages


parser = Parser()
parser.language = Language(tsp.language())
VALID = {"import_statement", "import_from_statement"}


def process_file(path: Path) -> list[str]:
    path = Path(path)
    src = path.read_bytes()
    tree = parser.parse(src)
    root = tree.root_node
    return [src[node.start_byte : node.end_byte].decode() for node in root.children if node.type in VALID]


def normalize_import(import_line: str) -> str | None:
    line = import_line.lower().strip()
    if line.startswith("import "):
        module = line[7:]
        if " as " in module:
            module = module[: module.index(" as ")]
        if "." in module:
            module = module[: module.index(".")]
        return module if module and not module.startswith("_") else None
    elif line.startswith("from "):
        module = line[5:]
        if module.startswith("."):
            return None
        if " import" in module:
            module = module[: module.index(" import")]
        if " as " in module:
            module = module[: module.index(" as ")]
        if "." in module:
            module = module[: module.index(".")]
        return module if module and not module.startswith("_") else None
    return None


def process_files_parallel(files: list[Path]) -> set[str]:
    all_imports = set()
    with ProcessPoolExecutor() as executor:
        future_to_file = {executor.submit(process_file, path): path for path in files}
        for future in as_completed(future_to_file):
            try:
                imports = future.result()
                all_imports.update(imports)
            except Exception as e:
                path = future_to_file[future]
                cprint(f"Error processing {path}: {e}", "yellow")
    return all_imports


def filter_imports(imports: set[str]) -> list[str]:
    stdlib_set = set(STDLIB)
    installed_pkgs = {pkg.replace("-", "_").lower() for pkg in get_installed_pkgs()}
    excluded = stdlib_set | installed_pkgs
    filtered = []
    for imp in imports:
        normalized = normalize_import(imp)
        if normalized and normalized not in excluded:
            filtered.append(normalized + "\n")
    return sorted(set(filtered))


def main() -> None:
    outfile = Path("importz.txt")
    cwd = Path.cwd()
    pyfiles = get_pyfiles(cwd)
    cprint(f"{len(pyfiles)} python files found", "green")
    all_imports = process_files_parallel(pyfiles)
    filtered_imports = filter_imports(all_imports)
    outfile.write_text("".join(filtered_imports), encoding="utf-8")
    for imp in filtered_imports:
        print(imp.strip())


if __name__ == "__main__":
    sys.exit(main())
