#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import shutil
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def remove_items_fast(items) -> None:
    with ThreadPoolExecutor(max_workers=32) as ex:
        ex.map(lambda p: shutil.rmtree(p) if p.is_dir() else p.unlink(), items)


def compress_and_cleanup(root: Path = Path()) -> None:
    root = root.resolve()
    archive_name = f"{root.name}.tar.gz"
    archive_path = root.parent / archive_name
    print(f"Creating archive: {archive_path}")
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    print("Archive created. Removing original files...")
    items = []
    for item in root.iterdir():
        if item.resolve() == archive_path:
            continue
        items.append(item)
    remove_items_fast(items)
    print("Cleanup complete.")


if __name__ == "__main__":
    compress_and_cleanup()
