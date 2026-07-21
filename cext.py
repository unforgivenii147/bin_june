#!/data/data/com.termux/files/usr/bin/env python


"""
Python Code Entity Extractor
Extracts classes, functions, methods, and constants from Python files and archives.
"""

from __future__ import annotations
import argparse
import ast
import io
import os
import re
import shutil
import sys
import tarfile
import textwrap
import zipfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple

try:
    import tree_sitter
    import tree_sitter_python as tspython

    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
try:
    import zstd

    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False


class Entity(NamedTuple):
    name: str
    full_name: str
    entity_type: str
    source: str
    imports: list[str]
    source_path: str


CONST_RE = re.compile("^[A-Z_][A-Z0-9_]*$")
IMPORT_HINTS: dict[str, str] = {
    "List": "from typing import List",
    "Dict": "from typing import Dict",
    "Optional": "from typing import Optional",
    "Tuple": "from typing import Tuple",
    "Set": "from typing import Set",
    "Any": "from typing import Any",
    "Union": "from typing import Union",
    "Callable": "from typing import Callable",
    "Type": "from typing import Type",
    "ClassVar": "from typing import ClassVar",
    "Final": "from typing import Final",
    "Literal": "from typing import Literal",
    "Generator": "from typing import Generator",
    "Iterator": "from typing import Iterator",
    "Iterable": "from typing import Iterable",
    "Sequence": "from typing import Sequence",
    "Mapping": "from typing import Mapping",
    "TypeVar": "from typing import TypeVar",
    "overload": "from typing import overload",
    "cast": "from typing import cast",
    "TYPE_CHECKING": "from typing import TYPE_CHECKING",
    "dataclass": "from dataclasses import dataclass",
    "field": "from dataclasses import field",
    "Path": "from pathlib import Path",
    "datetime": "from datetime import datetime",
    "date": "from datetime import date",
    "timedelta": "from datetime import timedelta",
    "re": "import re",
    "json": "import json",
    "os": "import os",
    "sys": "import sys",
    "math": "import math",
    "time": "import time",
    "copy": "import copy",
    "abc": "import abc",
    "ABC": "from abc import ABC",
    "abstractmethod": "from abc import abstractmethod",
    "functools": "import functools",
    "itertools": "import itertools",
    "collections": "import collections",
    "defaultdict": "from collections import defaultdict",
    "OrderedDict": "from collections import OrderedDict",
    "Counter": "from collections import Counter",
    "deque": "from collections import deque",
    "namedtuple": "from collections import namedtuple",
    "contextmanager": "from contextlib import contextmanager",
    "asynccontextmanager": "from contextlib import asynccontextmanager",
    "partial": "from functools import partial",
    "wraps": "from functools import wraps",
    "lru_cache": "from functools import lru_cache",
    "cached_property": "from functools import cached_property",
    "Enum": "from enum import Enum",
    "auto": "from enum import auto",
    "IntEnum": "from enum import IntEnum",
    "logging": "import logging",
    "getLogger": "import logging",
    "traceback": "import traceback",
    "threading": "import threading",
    "asyncio": "import asyncio",
    "subprocess": "import subprocess",
    "tempfile": "import tempfile",
    "hashlib": "import hashlib",
    "base64": "import base64",
    "struct": "import struct",
    "io": "import io",
    "StringIO": "from io import StringIO",
    "BytesIO": "from io import BytesIO",
    "socket": "import socket",
    "uuid": "import uuid",
    "warnings": "import warnings",
    "weakref": "import weakref",
    "inspect": "import inspect",
    "textwrap": "import textwrap",
    "string": "import string",
    "random": "import random",
    "heapq": "import heapq",
    "bisect": "import bisect",
    "array": "import array",
    "pickle": "import pickle",
    "shelve": "import shelve",
    "sqlite3": "import sqlite3",
    "csv": "import csv",
    "configparser": "import configparser",
    "argparse": "import argparse",
    "shutil": "import shutil",
    "glob": "import glob",
    "fnmatch": "import fnmatch",
    "stat": "import stat",
    "platform": "import platform",
    "signal": "import signal",
    "atexit": "import atexit",
    "pprint": "import pprint",
    "unittest": "import unittest",
    "pytest": "import pytest",
    "dataclasses": "import dataclasses",
    "typing_extensions": "import typing_extensions",
    "Protocol": "from typing import Protocol",
    "runtime_checkable": "from typing import runtime_checkable",
}


def detect_needed_imports(source: str) -> list[str]:
    needed: list[str] = []
    seen: set[str] = set()
    for name, stmt in IMPORT_HINTS.items():
        if re.search(f"\\b{re.escape(name)}\\b", source) and stmt not in seen:
            needed.append(stmt)
            seen.add(stmt)
    return needed


class EntityVisitor(ast.NodeVisitor):
    def __init__(self, source_lines: list[str], source_path: str) -> None:
        self.source_lines = source_lines
        self.source_path = source_path
        self.entities: list[Entity] = []
        self.imports: list[str] = []
        self._class_stack: list[str] = []

    def _slice(self, node: ast.AST) -> str:
        start = node.lineno - 1
        end = node.end_lineno
        lines = self.source_lines[start:end]
        col = node.col_offset
        stripped = [l[col:] if len(l) > col else l for l in lines]
        return "".join(stripped)

    def _record_import(self, node: ast.Import | ast.ImportFrom) -> None:
        src = ast.unparse(node)
        if src not in self.imports:
            self.imports.append(src)

    def visit_Import(self, node: ast.Import) -> None:
        self._record_import(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._record_import(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        class_source = self._slice(node)
        imports_in_class = detect_needed_imports(class_source)
        entity = Entity(
            name=node.name,
            full_name=node.name,
            entity_type="class",
            source=class_source,
            imports=imports_in_class,
            source_path=self.source_path,
        )
        self.entities.append(entity)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit_method(child, node.name)
            elif isinstance(child, ast.ClassDef):
                self.visit_ClassDef(child)
        self._class_stack.pop()

    def _visit_method(self, node: ast.FunctionDef | ast.AsyncFunctionDef, class_name: str) -> None:
        method_source = self._slice(node)
        full_name = f"{class_name}_{node.name}"
        imports_for_method = detect_needed_imports(method_source)
        entity = Entity(
            name=node.name,
            full_name=full_name,
            entity_type="function",
            source=method_source,
            imports=imports_for_method,
            source_path=self.source_path,
        )
        self.entities.append(entity)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._class_stack:
            return
        func_source = self._slice(node)
        imports_for_func = detect_needed_imports(func_source)
        entity = Entity(
            name=node.name,
            full_name=node.name,
            entity_type="function",
            source=func_source,
            imports=imports_for_func,
            source_path=self.source_path,
        )
        self.entities.append(entity)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        if self._class_stack:
            return
        for target in node.targets:
            if isinstance(target, ast.Name) and CONST_RE.match(target.id):
                const_source = self._slice(node)
                entity = Entity(
                    name=target.id,
                    full_name=target.id,
                    entity_type="const",
                    source=const_source,
                    imports=[],
                    source_path=self.source_path,
                )
                self.entities.append(entity)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._class_stack:
            return
        target = node.target
        if isinstance(target, ast.Name) and CONST_RE.match(target.id):
            const_source = self._slice(node)
            entity = Entity(
                name=target.id,
                full_name=target.id,
                entity_type="const",
                source=const_source,
                imports=[],
                source_path=self.source_path,
            )
            self.entities.append(entity)


def extract_imports_tree_sitter(source: str) -> list[str]:
    if not HAS_TREE_SITTER:
        return []
    try:
        PY_LANGUAGE = tree_sitter.Language(tspython.language())
        parser = tree_sitter.Parser(PY_LANGUAGE)
        tree = parser.parse(source.encode())
        imports: list[str] = []
        cursor = tree.walk()

        def _walk(node: tree_sitter.Node) -> None:
            if node.type in ("import_statement", "import_from_statement"):
                imports.append(node.text.decode(errors="replace"))
            for child in node.children:
                _walk(child)

        _walk(tree.root_node)
        return imports
    except Exception:
        return []


def parse_python_source(source: str, virtual_path: str) -> tuple[list[Entity], list[str]]:
    try:
        tree = ast.parse(source, filename=virtual_path)
    except SyntaxError as exc:
        print(f"  [warn] syntax error in {virtual_path}: {exc}", file=sys.stderr)
        return ([], [])
    lines = [l + "\n" for l in source.splitlines()]
    visitor = EntityVisitor(lines, virtual_path)
    visitor.visit(tree)
    ts_imports = extract_imports_tree_sitter(source)
    all_imports = ts_imports if ts_imports else visitor.imports
    return (visitor.entities, all_imports)


PYTHON_EXTENSIONS = {".py"}
ARCHIVE_EXTENSIONS = {".zip", ".whl", ".tar", ".gz", ".tgz", ".zst", ".xz"}
SKIP_DIRS = {".git", "__pycache__"}


def _looks_like_python(data: bytes) -> bool:
    head = data[:512]
    if b"#!/usr/bin/env python" in head or b"#!/usr/bin/python" in head:
        return True
    return any((kw in head for kw in (b"import ", b"def ", b"class ", b"if __name__")))


def read_py_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError) as exc:
        print(f"  [error] cannot read {path}: {exc}", file=sys.stderr)
        return None


def process_python_file(
    path: Path, virtual_path: str | None = None, source_override: str | None = None
) -> tuple[list[Entity], list[str]]:
    vpath = virtual_path or str(path)
    source = source_override if source_override is not None else read_py_file(path)
    if source is None:
        return ([], [])
    if not source.strip():
        return ([], [])
    return parse_python_source(source, vpath)


def process_zip_archive(archive_path: Path) -> list[tuple[list[Entity], list[str]]]:
    results: list[tuple[list[Entity], list[str]]] = []
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.infolist():
                name = member.filename
                if name.endswith("/"):
                    continue
                p = Path(name)
                is_py = p.suffix == ".py"
                if not is_py:
                    try:
                        data = zf.read(member)
                        is_py = _looks_like_python(data)
                        source = data.decode("utf-8", errors="replace") if is_py else None
                    except Exception:
                        continue
                else:
                    try:
                        source = zf.read(member).decode("utf-8", errors="replace")
                    except Exception:
                        continue
                if is_py and source:
                    vpath = f"{archive_path.name}::{name}"
                    results.append(parse_python_source(source, vpath))
    except (zipfile.BadZipFile, OSError) as exc:
        print(f"  [error] bad zip {archive_path}: {exc}", file=sys.stderr)
    return results


def _open_tar(archive_path: Path) -> tarfile.TarFile | None:
    suffix = "".join(archive_path.suffixes).lower()
    try:
        if suffix.endswith((".zst", ".tar.zst")):
            if not HAS_ZSTD:
                print(f"  [warn] zstd not available, skipping {archive_path}", file=sys.stderr)
                return None
            raw = zstd.decompress(archive_path.read_bytes())
            return tarfile.open(fileobj=io.BytesIO(raw))
        return tarfile.open(archive_path, mode="r:*")
    except (tarfile.TarError, OSError) as exc:
        print(f"  [error] cannot open tar {archive_path}: {exc}", file=sys.stderr)
        return None


def process_tar_archive(archive_path: Path) -> list[tuple[list[Entity], list[str]]]:
    results: list[tuple[list[Entity], list[str]]] = []
    tf = _open_tar(archive_path)
    if tf is None:
        return results
    with tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            name = member.name
            p = Path(name)
            is_py = p.suffix == ".py"
            try:
                fobj = tf.extractfile(member)
                if fobj is None:
                    continue
                data = fobj.read()
            except Exception:
                continue
            if not is_py:
                is_py = _looks_like_python(data)
            if is_py:
                source = data.decode("utf-8", errors="replace")
                vpath = f"{archive_path.name}::{name}"
                results.append(parse_python_source(source, vpath))
    return results


def process_archive(archive_path: Path) -> list[tuple[list[Entity], list[str]]]:
    name = archive_path.name.lower()
    if name.endswith((".whl", ".zip")):
        return process_zip_archive(archive_path)
    return process_tar_archive(archive_path)


def _is_archive(path: Path) -> bool:
    name = path.name.lower()
    return any((name.endswith(ext) for ext in (".whl", ".zip", ".tar.gz", ".tgz", ".tar.zst", ".tar.xz", ".tar")))


def discover_files(root: Path) -> tuple[list[Path], list[Path]]:
    py_files: list[Path] = []
    archives: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and (not Path(dirpath, d).is_symlink())]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.is_symlink():
                continue
            if fpath.suffix == ".py":
                py_files.append(fpath)
            elif _is_archive(fpath):
                archives.append(fpath)
            else:
                try:
                    if fpath.stat().st_size < 1000000:
                        data = fpath.read_bytes()
                        if _looks_like_python(data):
                            py_files.append(fpath)
                except (OSError, PermissionError):
                    pass
    return (py_files, archives)


def _worker_py(path: Path) -> tuple[list[Entity], list[str], str]:
    entities, imports = process_python_file(path)
    return (entities, imports, str(path))


def _worker_archive(path: Path) -> tuple[list[Entity], list[str], str]:
    all_entities: list[Entity] = []
    all_imports: list[str] = []
    for entities, imports in process_archive(path):
        all_entities.extend(entities)
        all_imports.extend(imports)
    return (all_entities, all_imports, str(path))


TYPE_SUBDIR = {"function": "function", "class": "class", "const": "const"}


def _safe_filename(base: str) -> str:
    return re.sub("[^\\w\\-.]", "_", base)


def _unique_path(directory: Path, stem: str, suffix: str = ".py") -> Path:
    candidate = directory / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def write_entity(entity: Entity, output_dir: Path) -> Path | None:
    subdir = output_dir / TYPE_SUBDIR.get(entity.entity_type, "other")
    subdir.mkdir(parents=True, exist_ok=True)
    stem = _safe_filename(entity.full_name)
    out_path = _unique_path(subdir, stem)
    header = f"# Source: {entity.source_path}\n\n"
    all_imports = sorted(set(entity.imports), key=lambda s: 0 if s.startswith(("import ", "from ")) else 1)
    import_block = "\n".join(all_imports)
    if import_block:
        import_block += "\n\n"
    content = header + import_block + entity.source
    if not content.endswith("\n"):
        content += "\n"
    try:
        out_path.write_text(content, encoding="utf-8")
        return out_path
    except OSError as exc:
        print(f"  [error] cannot write {out_path}: {exc}", file=sys.stderr)
        return None


def write_global_imports(imports: list[str], output_dir: Path) -> None:
    unique = sorted(set(imports))
    content = "# Global imports collected from all processed files\n\n"
    content += "\n".join(unique) + "\n"
    out = output_dir / "global_imports.py"
    try:
        out.write_text(content, encoding="utf-8")
        print(f"\nGlobal imports saved → {out}")
    except OSError as exc:
        print(f"  [error] cannot write global imports: {exc}", file=sys.stderr)


def report(entities: list[Entity], all_imports: list[str], saved_count: int) -> None:
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    by_type: dict[str, int] = defaultdict(int)
    for e in entities:
        by_type[e.entity_type] += 1
    for etype, count in sorted(by_type.items()):
        print(f"  {etype:<12}: {count}")
    print(f"  {'total':<12}: {len(entities)}")
    print(f"  {'saved':<12}: {saved_count}")
    module_counts: dict[str, int] = defaultdict(int)
    for stmt in all_imports:
        m = re.match("(?:from|import)\\s+([\\w.]+)", stmt)
        if m:
            module_counts[m.group(1)] += 1
    if module_counts:
        print("\nTop imported modules:")
        for mod, cnt in sorted(module_counts.items(), key=lambda x: -x[1])[:15]:
            print(f"  {mod:<30} {cnt}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract Python code entities from files and archives.")
    parser.add_argument("-t", "--tmp", action="store_true", help="Write output to ~/tmp/output/ instead of ./output/")
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=min(os.cpu_count() or 1, 8),
        help="Number of parallel workers (default: min(cpu_count, 8))",
    )
    parser.add_argument(
        "-d", "--dir", type=Path, default=Path.cwd(), help="Root directory to scan (default: current directory)"
    )
    args = parser.parse_args(argv)
    output_dir: Path = Path.home() / "tmp" / "output" if args.tmp else Path.cwd() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    root: Path = args.dir.resolve()
    print(f"Scanning: {root}")
    print("\nDiscovering files…")
    py_files, archives = discover_files(root)
    print(f"  Found {len(py_files)} Python files and {len(archives)} archive(s).")
    if not py_files and (not archives):
        print("Nothing to process.")
        return 0
    all_entities: list[Entity] = []
    all_imports: list[str] = []
    tasks: list[tuple[callable, Path]] = [(_worker_py, p) for p in py_files] + [(_worker_archive, p) for p in archives]
    print(f"\nProcessing {len(tasks)} file(s) with {args.workers} worker(s)…")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        future_map = {pool.submit(fn, path): path for fn, path in tasks}
        for future in as_completed(future_map):
            path = future_map[future]
            try:
                entities, imports, label = future.result()
                print(f"  ✓ {label}  ({len(entities)} entities)")
                all_entities.extend(entities)
                all_imports.extend(imports)
            except Exception as exc:
                print(f"  ✗ {path}: {exc}", file=sys.stderr)
    print(f"\nWriting {len(all_entities)} entities…")
    saved = 0
    for entity in all_entities:
        if write_entity(entity, output_dir):
            saved += 1
    write_global_imports(all_imports, output_dir)
    report(all_entities, all_imports, saved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
