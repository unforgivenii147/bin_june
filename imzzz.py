#!/data/data/com.termux/files/usr/bin/env python
import ast
import multiprocessing as mp
import os
import tarfile
import zipfile
from pathlib import Path

from dh import PKG_MAPPING, STDLIB

STD_LIB = STDLIB
MAPPING = PKG_MAPPING
try:
    with Path("/sdcard/pip.txt").open("r", encoding="utf-8") as f:
        PIP_PACKAGES = {line.strip().split("==")[0].split("[")[0] for line in f if line.strip()}
except FileNotFoundError:
    PIP_PACKAGES = set()


def is_python_file(file_path):
    return (
        file_path.suffix == ".py"
        or not file_path.suffix
        and any(
            line.startswith(("import ", "from ", "#!/usr/bin/env python"))
            for line in Path(file_path).open(encoding="utf-8", errors="ignore")
        )
    )


def extract_compressed(file_path, extract_to) -> None:
    if file_path.suffix == ".zip":
        with zipfile.ZipFile(file_path, "r") as z:
            z.extractall(extract_to)
    elif file_path.suffix in {".tar.gz", ".tar.xz", ".tar.zst"}:
        with tarfile.open(file_path, "r:*") as tar:
            tar.extractall(extract_to)
    elif file_path.suffix == ".whl":
        with zipfile.ZipFile(file_path, "r") as z:
            z.extractall(extract_to)


def get_imports(file_path):
    imports = set()
    try:
        with Path(file_path).open(encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module not in STD_LIB and not module.startswith(".") and not file_path.parent.match(f"*{module}*"):
                    imports.add(MAPPING.get(module, module))
        elif isinstance(node, ast.ImportFrom):
            module = node.module.split(".")[0] if node.module else ""
            if (
                module
                and module not in STD_LIB
                and not module.startswith(".")
                and not file_path.parent.match(f"*{module}*")
            ):
                imports.add(MAPPING.get(module, module))
    return imports


def process_file(file_path):
    path = Path(path)
    if file_path.is_dir():
        return set()
    if file_path.suffix in {".zip", ".whl", ".tar.gz", ".tar.xz", ".tar.zst"}:
        extract_dir = file_path.parent / f"extracted_{file_path.stem}"
        extract_compressed(file_path, extract_dir)
        imports = set()
        for root, _, files in os.walk(extract_dir):
            for f in files:
                f_path = Path(root) / f
                if is_python_file(f_path):
                    imports.update(get_imports(f_path))
        return imports
    if is_python_file(file_path):
        return get_imports(file_path)
    return set()


def main() -> None:
    root = Path()
    python_files = []
    for ext in ("*.py", "*"):
        python_files.extend(root.rglob(ext))
    with mp.Pool() as pool:
        results = pool.map(process_file, python_files)
    all_imports = set().union(*results)
    requirements = sorted(all_imports & PIP_PACKAGES)
    with Path("requirements.txt").open("w", encoding="utf-8") as f:
        f.writelines(f"{req}\n" for req in requirements)


if __name__ == "__main__":
    main()
