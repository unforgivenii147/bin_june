#!/data/data/com.termux/files/usr/bin/python

"""
AST-based duplicate definition extractor.
Finds repeated functions, classes, and constant assignments across all
Python files (including compressed archives) in the current directory tree.
Optionally copies (-c) or moves (-m) the duplicate definitions to
`utils/const.py`, `utils/class.py`, `utils/func.py`.
Supported compression: gzip, bz2, lzma, zstandard (.zst), brotli (.br).
Multiprocessing is used for fast AST analysis. Logging is handled by loguru.
Requires Python 3.9+ (for ast.unparse).
"""

import argparse
import ast
import concurrent.futures
import gzip
import hashlib
import lzma
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
_COMPRESSED_EXT: Dict[str, object] = {
    ".gz": gzip,
    ".bz2": gzip,
    ".xz": lzma,
    ".lzma": lzma,
    ".zst": None,
    ".br": None,
}


def _decompress_file(path: Path) -> Optional[str]:
    """Return decompressed source if *path* is a compressed ``.py`` file, else ``None``."""
    suffix = path.suffix.lower()
    if suffix not in _COMPRESSED_EXT:
        return None
    stem = path.stem
    if not stem.endswith(".py"):
        return None
    try:
        if suffix == ".zst":
            import zstandard as zstd

            with open(path, "rb") as fh:
                dctx = zstd.ZstdDecompressor()
                data = dctx.decompress(fh.read())
            return data.decode("utf-8", errors="replace")
        if suffix == ".br":
            import brotli

            with open(path, "rb") as fh:
                data = brotli.decompress(fh.read())
            return data.decode("utf-8", errors="replace")
        if suffix in (".gz", ".bz2"):
            module = gzip if suffix == ".gz" else __import__("bz2")
        else:
            module = _COMPRESSED_EXT[suffix]
        with module.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except ImportError as exc:
        logger.error("Missing library to handle {}: {}", suffix, exc)
        return None
    except Exception as exc:
        logger.error("Failed to decompress {}: {}", path, exc)
        return None


def _find_files(root: str = ".") -> List[Tuple[str, Optional[str]]]:
    """Walk *root* recursively; return ``(path, source_or_None)`` tuples.
    For plain ``.py`` files ``source`` is ``None`` (deferred read).
    For compressed files the decompressed source is returned directly.
    """
    results: List[Tuple[str, Optional[str]]] = []
    root_path = Path(root).resolve()
    utils_path = root_path / "utils"
    for dirpath, _, filenames in os.walk(root):
        if Path(dirpath).resolve() == utils_path:
            continue
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            path = Path(full)
            if path.suffix == ".py":
                results.append((full, None))
            else:
                source = _decompress_file(path)
                if source is not None:
                    results.append((full, source))
    return results


def _hash(source: str) -> str:
    """SHA-256 hex digest of *source*."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


@dataclass
class _Def:
    type: str
    name: str
    source_code: str
    content_hash: str
    filepath: str


def _extract_definitions(path: str, source: str) -> List[_Def]:
    """Parse *source* and return top-level function/class/constant definitions."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        logger.error("Syntax error in {}: {}", path, exc)
        return []
    defs: List[_Def] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            typ, name = ("func", node.name)
        elif isinstance(node, ast.ClassDef):
            typ, name = ("class", node.name)
        elif isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                typ, name = ("const", node.targets[0].id)
            else:
                continue
        else:
            continue
        try:
            segment = ast.get_source_segment(source, node)
        except Exception as exc:
            logger.error("Failed to get source segment in {} for {}: {}", path, name, exc)
            continue
        if segment is None:
            continue
        segment = segment.strip("\n")
        defs.append(
            _Def(
                type=typ,
                name=name,
                source_code=segment,
                content_hash=_hash(segment),
                filepath=path,
            )
        )
    return defs


def _new_utils_entries(groups: Dict[str, List[_Def]], existing: Dict[str, Dict[str, _Def]]) -> Dict[str, List[_Def]]:
    """Determine which duplicate groups should be added to the utils files."""
    new: Dict[str, List[_Def]] = {"func": [], "class": [], "const": []}
    for hash_key, defs in groups.items():
        rep = defs[0]
        typ, name = (rep.type, rep.name)
        if typ not in existing:
            existing[typ] = {}
        if name in existing[typ]:
            if existing[typ][name].content_hash == rep.content_hash:
                logger.debug("Already in {}.py: {}", typ, name)
                continue
            logger.warning(
                "Conflict in {}.py: '{}' exists with different content – skipping.",
                typ,
                name,
            )
            continue
        if any((d.name == name for d in new[typ])):
            continue
        new[typ].append(rep)
    return new


def _read_existing_utils(utils_dir: Path) -> Dict[str, Dict[str, _Def]]:
    """Parse existing ``utils/*.py`` and return ``{type: {name: _Def}}``."""
    existing: Dict[str, Dict[str, _Def]] = {"func": {}, "class": {}, "const": {}}
    for typ, fname in [
        ("func", "func.py"),
        ("class", "class.py"),
        ("const", "const.py"),
    ]:
        path = utils_dir / fname
        if path.is_file():
            try:
                src = path.read_text(encoding="utf-8")
                for d in _extract_definitions(str(path), src):
                    existing[typ][d.name] = d
            except Exception as exc:
                logger.error("Error parsing existing {}: {}", path, exc)
    return existing


def _write_utils_files(utils_dir: Path, new: Dict[str, List[_Def]]) -> None:
    """Append new definitions to the appropriate utils files."""
    utils_dir.mkdir(exist_ok=True)
    for typ, fname in [
        ("func", "func.py"),
        ("class", "class.py"),
        ("const", "const.py"),
    ]:
        if not new[typ]:
            continue
        path = utils_dir / fname
        write_header = not path.exists() or path.stat().st_size == 0
        with open(path, "a", encoding="utf-8") as fh:
            if write_header:
                fh.write(f"# {typ.capitalize()} definitions\n\n")
            for d in new[typ]:
                fh.write(d.source_code + "\n\n")
        logger.info("Added {} definition(s) to {}", len(new[typ]), fname)


def _move_definitions(groups: Dict[str, List[_Def]]) -> None:
    """
    Remove moved definitions from regular ``.py`` files.
    Only plain files are modified (compressed archives are left untouched).
    The resulting source is validated with ``ast.parse``; if a syntax error
    occurs the file is **not** overwritten.
    """
    to_remove: Dict[str, Set[str]] = {}
    for hash_key, defs in groups.items():
        for d in defs:
            if not d.filepath.endswith(".py") or any((d.filepath.endswith(ext) for ext in _COMPRESSED_EXT)):
                continue
            to_remove.setdefault(d.filepath, set()).add(hash_key)
    for path, hashes in to_remove.items():
        try:
            source = Path(path).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=path)
            new_body = []
            for node in tree.body:
                try:
                    segment = ast.get_source_segment(source, node)
                except Exception:
                    new_body.append(node)
                    continue
                if segment is None:
                    new_body.append(node)
                    continue
                node_hash = _hash(segment.strip("\n"))
                if node_hash in hashes:
                    continue
                new_body.append(node)
            if len(new_body) == len(tree.body):
                continue
            tree.body = new_body
            new_source = ast.unparse(tree)
            try:
                ast.parse(new_source)
            except SyntaxError as exc:
                logger.error("Resulting code of {} has a syntax error – skipping: {}", path, exc)
                continue
            Path(path).write_text(new_source, encoding="utf-8")
            logger.info("Removed {} duplicate definition(s) from {}", len(hashes), path)
        except Exception as exc:
            logger.error("Failed to process {} for moving: {}", path, exc)


def main() -> None:
    if sys.version_info < (3, 9):
        logger.error("Python 3.9+ is required (ast.unparse).")
        sys.exit(1)
    parser = argparse.ArgumentParser(description="Copy/move repeated Python definitions to utils/")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--copy", action="store_true", help="Copy duplicates to utils/")
    group.add_argument(
        "-m",
        "--move",
        action="store_true",
        help="Move duplicates to utils/ and remove from originals",
    )
    args = parser.parse_args()
    action = "copy" if args.copy else "move"
    logger.info("Action: {}", action)
    logger.info("Scanning for Python files …")
    files = _find_files(".")
    file_jobs: List[Tuple[str, str]] = []
    for path, source in files:
        if source is None:
            try:
                source = Path(path).read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                logger.error("Failed to read {}: {}", path, exc)
                continue
        file_jobs.append((path, source))
    logger.info("Found {} file(s) to process", len(file_jobs))
    all_defs: List[_Def] = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {executor.submit(_extract_definitions, p, src): p for p, src in file_jobs}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result:
                    all_defs.extend(result)
            except Exception as exc:
                logger.error("Worker failed: {}", exc)
    groups: Dict[str, List[_Def]] = {}
    for d in all_defs:
        groups.setdefault(d.content_hash, []).append(d)
    duplicate_groups = {h: defs for h, defs in groups.items() if len(defs) > 1}
    logger.info("Found {} duplicate group(s)", len(duplicate_groups))
    if not duplicate_groups:
        logger.info("No duplicates – nothing to do.")
        return
    utils_dir = Path("utils")
    existing = _read_existing_utils(utils_dir) if utils_dir.exists() else {}
    new_entries = _new_utils_entries(duplicate_groups, existing)
    total_new = sum((len(lst) for lst in new_entries.values()))
    if total_new == 0:
        logger.info("All duplicates are already present in utils/ – nothing to add.")
        return
    _write_utils_files(utils_dir, new_entries)
    if action == "move":
        _move_definitions(duplicate_groups)


if __name__ == "__main__":
    main()
