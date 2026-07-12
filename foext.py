#!/data/data/com.termux/files/usr/bin/env python


import shutil
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


BASE_DIR = Path.cwd()
for item in BASE_DIR.iterdir():
    if not item.is_file():
        continue
    ext = item.suffix.lower().lstrip(".") or "no_extension"
    target_dir = BASE_DIR / ext
    target_dir.mkdir(exist_ok=True)
    shutil.move(str(item), target_dir / item.name)
