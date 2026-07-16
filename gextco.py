#!/data/data/com.termux/files/usr/bin/env python

"""
Extract entities (classes, functions, constants) from Python files recursively.

Features:
- Recursive directory traversal using pathlib
- Parallel processing with multiprocessing
- Progress tracking with tqdm
- Saves unique entities to separate files
- Extracts and saves imports
"""

import ast
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Set

from tqdm import tqdm

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    name: str
    file_path: str
    line_number: int


@dataclass
class ExtractionResult:
    file_path: Path
    classes: List[Entity]
    functions: List[Entity]
    constants: List[Entity]
    imports: Set[str]


class EntityExtractor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.classes: List[Entity] = []
        self.functions: List[Entity] = []
        self.constants: List[Entity] = []
        self.imports: Set[str] = set()
        self._in_class = False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append(Entity(name=node.name, file_path=str(self.file_path), line_number=node.lineno))
        old_in_class = self._in_class
        self._in_class = True
        self.generic_visit(node)
        self._in_class = old_in_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if not self._in_class:
            self.functions.append(Entity(name=node.name, file_path=str(self.file_path), line_number=node.lineno))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if not self._in_class:
            self.functions.append(Entity(name=node.name, file_path=str(self.file_path), line_number=node.lineno))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if not self._in_class:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id.isupper():
                        self.constants.append(
                            Entity(
                                name=target.id,
                                file_path=str(self.file_path),
                                line_number=node.lineno,
                            )
                        )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(f"import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            self.imports.add(f"from {module} import {alias.name}")
        self.generic_visit(node)


def extract_from_file(file_path: Path) -> ExtractionResult:
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
        extractor = EntityExtractor(file_path)
        extractor.visit(tree)
        return ExtractionResult(
            file_path=file_path,
            classes=extractor.classes,
            functions=extractor.functions,
            constants=extractor.constants,
            imports=extractor.imports,
        )
    except (SyntaxError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return ExtractionResult(file_path=file_path, classes=[], functions=[], constants=[], imports=set())


def find_python_files(root_dir: Path) -> List[Path]:
    return list(root_dir.rglob("*.py"))


def save_entities(
    output_dir: Path,
    entity_type: str,
    entities_by_file: Dict[str, List[Entity]],
    unique_entities: Set[str],
) -> None:
    entity_dir = output_dir / entity_type
    entity_dir.mkdir(parents=True, exist_ok=True)
    for file_path, entities in entities_by_file.items():
        if entities:
            file_name = Path(file_path).stem + ".txt"
            output_file = entity_dir / file_name
            with open(output_file, "w", encoding="utf-8") as f:
                for entity in sorted(entities, key=lambda e: e.name):
                    f.write(f"{entity.name} (line {entity.line_number})\n")
    unique_file = entity_dir / "unique.txt"
    with open(unique_file, "w", encoding="utf-8") as f:
        for name in sorted(unique_entities):
            f.write(f"{name}\n")
    logger.info(f"Saved {len(unique_entities)} unique {entity_type}")


def save_imports(output_dir: Path, imports_by_dir: Dict[str, Set[str]]) -> None:
    imports_dir = output_dir / "imports"
    imports_dir.mkdir(parents=True, exist_ok=True)
    for dir_name, imports in imports_by_dir.items():
        if imports:
            file_name = f"imports-{dir_name}.txt"
            output_file = imports_dir / file_name
            with open(output_file, "w", encoding="utf-8") as f:
                for imp in sorted(imports):
                    f.write(f"{imp}\n")
    logger.info(f"Saved imports for {len(imports_by_dir)} directories")


def main(root_dir: str = ".", output_dir: str = "output", num_workers: int = None) -> None:
    root_path = Path(root_dir)
    output_path = Path(output_dir)
    if not root_path.exists():
        logger.error(f"Root directory not found: {root_path}")
        sys.exit(1)
    logger.info(f"Scanning for Python files in {root_path}...")
    py_files = find_python_files(root_path)
    if not py_files:
        logger.warning("No Python files found.")
        return
    logger.info(f"Found {len(py_files)} Python files")
    num_workers = num_workers or cpu_count()
    logger.info(f"Using {num_workers} workers for parallel processing")
    entities_by_file = defaultdict(list)
    unique_classes = set()
    unique_functions = set()
    unique_constants = set()
    imports_by_dir = defaultdict(set)
    with Pool(num_workers) as pool:
        results = list(
            tqdm(
                pool.imap_unordered(extract_from_file, py_files),
                total=len(py_files),
                desc="Extracting entities",
                unit="file",
            )
        )
    logger.info("Aggregating results...")
    for result in results:
        for entity in result.classes:
            entities_by_file["classes"][result.file_path].append(entity)
            unique_classes.add(entity.name)
        for entity in result.functions:
            entities_by_file["functions"][result.file_path].append(entity)
            unique_functions.add(entity.name)
        for entity in result.constants:
            entities_by_file["constants"][result.file_path].append(entity)
            unique_constants.add(entity.name)
        dir_name = result.file_path.parent.name or "root"
        imports_by_dir[dir_name].update(result.imports)
    entities_by_file = {key: dict(val) for key, val in entities_by_file.items()}
    logger.info(f"Saving results to {output_path}...")
    output_path.mkdir(parents=True, exist_ok=True)
    save_entities(output_path, "class", entities_by_file.get("classes", {}), unique_classes)
    save_entities(output_path, "func", entities_by_file.get("functions", {}), unique_functions)
    save_entities(output_path, "const", entities_by_file.get("constants", {}), unique_constants)
    save_imports(output_path, imports_by_dir)
    logger.info("=" * 50)
    logger.info(f"Extraction Summary:")
    logger.info(f"  Files processed: {len(py_files)}")
    logger.info(f"  Unique classes: {len(unique_classes)}")
    logger.info(f"  Unique functions: {len(unique_functions)}")
    logger.info(f"  Unique constants: {len(unique_constants)}")
    logger.info(f"  Total imports: {sum(len(v) for v in imports_by_dir.values())}")
    logger.info("=" * 50)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract entities from Python files recursively")
    parser.add_argument("-r", "--root", default=".", help="Root directory to scan (default: current directory)")
    parser.add_argument("-o", "--output", default="output", help="Output directory (default: output)")
    parser.add_argument("-w", "--workers", type=int, help="Number of parallel workers (default: CPU count)")
    args = parser.parse_args()
    main(args.root, args.output, args.workers)
