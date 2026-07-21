#!/data/data/com.termux/files/usr/bin/env python

"""Module for ex_const.py."""

from __future__ import annotations

import ast
import logging
import operator
from os import scandir as os_scandir
from pathlib import Path

from joblib import Parallel, delayed
from xxhash import xxh64

CHUNK_SIZE = 1024 * 1024

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


OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "const.py"
LOG_FILE = OUTPUT_DIR / "error.log"
OUTPUT_DIR.mkdir(exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_file_hash(filepath: Path) -> str:
    hasher = xxh64()
    with Path(filepath).open("rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def extract_constants(filepath: Path) -> list[tuple[str, str, str]]:
    constants = []
    try:
        with Path(filepath).open("r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(filepath))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                is_simple_assign = all(isinstance(t, ast.Name) for t in node.targets)
                if is_simple_assign and isinstance(node.value, ast.Constant):
                    for target in node.targets:
                        const_name = target.id
                        if const_name.isupper():
                            const_value = ast.unparse(node.value)
                            const_type = type(node.value.value).__name__
                            constants.append((const_name, const_value, const_type))
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.value is not None:
                    if node.target.id.isupper():
                        const_name = node.target.id
                        const_value = ast.unparse(node.value)
                        const_type = (
                            type(node.value.value).__name__ if isinstance(node.value, ast.Constant) else "unknown"
                        )
                        constants.append((const_name, const_value, const_type))
    except SyntaxError as e:
        logging.error(f"Syntax error in {filepath}: {e}")
    except Exception as e:
        logging.error(f"Error processing {filepath}: {e}")
    return constants


def process_file(filepath: Path) -> tuple[str, list[tuple[str, str, str]] | None]:
    file_hash = get_file_hash(filepath)
    Path(path)
    constants = extract_constants(filepath)
    return file_hash, constants


def main() -> None:
    cwd = Path.cwd()
    python_files = list(get_pyfiles(cwd))
    if not python_files:
        print("No Python files found in the current directory.")
        return
    print(f"Found {len(python_files)} Python files. Processing...")
    results = Parallel(n_jobs=-1)(delayed(process_file)(f) for f in python_files)
    processed_hashes = set()
    all_constants_by_hash = {}
    for file_hash, constants in results:
        if constants is None:
            continue
        if file_hash not in processed_hashes:
            processed_hashes.add(file_hash)
            for name, value, ctype in constants:
                if file_hash not in all_constants_by_hash:
                    all_constants_by_hash[file_hash] = []
                found = False
                for idx, (existing_name, existing_value, _existing_type) in enumerate(all_constants_by_hash[file_hash]):
                    if existing_name == name and existing_value == value:
                        all_constants_by_hash[file_hash][idx] = name, value, ctype
                        found = True
                        break
                if not found:
                    all_constants_by_hash[file_hash].append((name, value, ctype))
    final_constants = []
    for file_hash, const_list in all_constants_by_hash.items():
        final_constants.extend(const_list)
    final_constants.sort(key=operator.itemgetter(0))
    with Path(OUTPUT_FILE).open("w", encoding="utf-8") as f:
        f.write("# Automatically generated constants file\n")
        f.write("# Based on files in the current directory\n\n")
        written_consts = set()
        for name, value, ctype in final_constants:
            constant_line = f"{name} = {value}"
            if constant_line not in written_consts:
                f.write(f"# Type: {ctype}\n")
                f.write(f"{constant_line}\n\n")
                written_consts.add(constant_line)
    print(f"Successfully extracted {len(written_consts)} unique constants to {OUTPUT_FILE}")
    if LOG_FILE.exists():
        print(f"Errors logged to {LOG_FILE}")


if __name__ == "__main__":
    main()