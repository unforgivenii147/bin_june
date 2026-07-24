#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import argparse
import ast
import bz2
import gzip
import hashlib
import lzma
import os
import tarfile
import zipfile
from ast import Module
from multiprocessing import Pool, cpu_count
from pathlib import Path

import brotli
import zstandard as zstd
from loguru import logger

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

logger.add("error.log", level="ERROR")
COMPRESSED_EXTENSIONS = [".zip", ".tar", ".gz", ".bz2", ".xz", ".zst", ".br"]


def copy_chunks(src, dst, chunk_size: int = 1024 * 1024) -> None:
    while True:
        chunk = src.read(chunk_size)
        if not chunk:
            break
        dst.write(chunk)


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def extract_archive(file_path, extract_to) -> None:
    try:
        if file_path.suffix == ".zip":
            with zipfile.ZipFile(file_path, "r") as z:
                z.extractall(extract_to)
        elif file_path.suffix == ".tar":
            with tarfile.open(file_path, "r") as t:
                t.extractall(extract_to)
        elif file_path.suffix == ".gz":
            with gzip.open(file_path, "rb") as g, open(extract_to / file_path.stem, "wb") as f:
                copy_chunks(g, f)
        elif file_path.suffix == ".bz2":
            with bz2.open(file_path, "rb") as b, open(extract_to / file_path.stem, "wb") as f:
                copy_chunks(b, f)
        elif file_path.suffix == ".xz":
            with lzma.open(file_path, "rb") as x, open(extract_to / file_path.stem, "wb") as f:
                copy_chunks(x, f)
        elif file_path.suffix == ".zst":
            with open(file_path, "rb") as z:
                dctx = zstd.ZstdDecompressor()
                with open(extract_to / file_path.stem, "wb") as f:
                    f.write(dctx.decompress(z.read()))
        elif file_path.suffix == ".br":
            with open(file_path, "rb") as b:
                decompressed_data = brotli.decompress(b.read())
                with open(extract_to / file_path.stem, "wb") as f:
                    f.write(decompressed_data)
    except Exception as e:
        logger.error(f"Error extracting {file_path}: {e}")


def parse_python_file(file_path) -> Module | None:
    try:
        with open(file_path, encoding="utf-8") as f:
            return ast.parse(f.read(), filename=str(file_path))
    except Exception as e:
        logger.error(f"Error parsing {file_path}: {e}")
        return None


def find_repeated_definitions(ast_tree: Module):
    definitions = {"functions": {}, "classes": {}, "constants": {}}
    for node in ast.walk(ast_tree):
        if isinstance(node, ast.FunctionDef):
            content = ast.unparse(node)
            content_hash = hash_content(content)
            definitions["functions"].setdefault(content_hash, []).append(node)
        elif isinstance(node, ast.ClassDef):
            content = ast.unparse(node)
            content_hash = hash_content(content)
            definitions["classes"].setdefault(content_hash, []).append(node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    content = ast.unparse(node)
                    content_hash = hash_content(content)
                    definitions["constants"].setdefault(content_hash, []).append(node)
    for key in definitions:
        definitions[key] = {k: v for k, v in definitions[key].items() if len(v) > 1}
    return definitions


def process_file(file_path):
    Path(path)
    """Process a single file to find repeated definitions."""
    ast_tree = parse_python_file(file_path)
    if ast_tree:
        return find_repeated_definitions(ast_tree)
    return None


def process_directory(directory):
    repeated_definitions = {"functions": {}, "classes": {}, "constants": {}}
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix == ".py":
                print(f"processing ... {file_path.name}")
                result = process_file(file_path)
                if result:
                    for key in repeated_definitions:
                        for content_hash, nodes in result[key].items():
                            repeated_definitions[key].setdefault(content_hash, []).extend(nodes)
    return repeated_definitions


def write_definitions_to_file(definitions, output_dir: Path, move=False) -> None:
    for def_type, items in definitions.items():
        file_name = f"{def_type[:-1]}.py"
        output_file = output_dir / file_name
        with open(output_file, "w", encoding="utf-8") as f:
            for nodes in items.values():
                for node in nodes:
                    content = ast.unparse(node)
                    try:
                        ast.parse(content)
                        f.write(content + "\n\n")
                        if move:
                            pass
                    except SyntaxError as e:
                        logger.error(f"Syntax error in {content}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Python files for repeated definitions.")
    parser.add_argument("-m", "--move", action="store_true", help="Move repeated definitions to utils directory.")
    parser.add_argument("-c", "--copy", action="store_true", help="Copy repeated definitions to utils directory.")
    args = parser.parse_args()
    cwd = Path.cwd()
    utils_dir = cwd / "utils"
    utils_dir.mkdir(exist_ok=True)
    print(cpu_count())
    with Pool(cpu_count()) as pool:
        results = pool.map(process_directory, [cwd])
    combined_results = {"functions": {}, "classes": {}, "constants": {}}
    for result in results:
        for key in combined_results:
            for content_hash, nodes in result[key].items():
                combined_results[key].setdefault(content_hash, []).extend(nodes)
    if args.move or args.copy:
        write_definitions_to_file(combined_results, utils_dir, move=args.move)


if __name__ == "__main__":
    main()
