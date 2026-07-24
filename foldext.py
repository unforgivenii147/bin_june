#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_size_str(size_bytes) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"


def folderize_by_extension(cwd: Path):
    root_path = Path(cwd)
    extension_stats = {}
    for file_path in root_path.rglob("*"):
        if ".git" in file_path.parts:
            continue
        if file_path.is_file():
            ext = file_path.suffix.lower()[1:] if file_path.suffix else "no_extension"
            size = file_path.stat().st_size
            if ext not in extension_stats:
                extension_stats[ext] = {"count": 0, "total_size": 0, "files": []}
            extension_stats[ext]["count"] += 1
            extension_stats[ext]["total_size"] += size
            extension_stats[ext]["files"].append(file_path)
    created_dirs = set()
    for ext, stats in extension_stats.items():
        target_dir = root_path / ext
        target_dir.mkdir(exist_ok=True)
        created_dirs.add(ext)
        for file_path in stats["files"]:
            if file_path.parent == target_dir:
                continue
            target_path = target_dir / file_path.name
            counter = 1
            while target_path.exists():
                target_path = target_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                counter += 1
            with contextlib.suppress(BaseException):
                shutil.move(str(file_path), str(target_path))
    for dir_path in sorted(root_path.glob("**/*"), key=lambda p: len(p.parts), reverse=True):
        if dir_path.is_dir() and dir_path != root_path:
            with contextlib.suppress(OSError):
                dir_path.rmdir()
    total_files = 0
    total_size = 0
    for ext in sorted(extension_stats.keys()):
        stats = extension_stats[ext]
        total_files += stats["count"]
        total_size += stats["total_size"]
        ext_display = ext if ext else "no_extension"
        size_str = get_size_str(stats["total_size"])
        print(f"{ext_display:<15} : {stats['count']:4} file{'s' if stats['count'] != 1 else ' '}  {size_str:>8}")
    print("-" * 50)
    print(f"{'TOTAL':<15} : {total_files:4} files  {get_size_str(total_size):>8}")
    print("=" * 50)
    return created_dirs, extension_stats


if __name__ == "__main__":
    target_dir = Path.cwd()
    created_dirs, stats = folderize_by_extension(target_dir)
    print(f"\nCreated {len(created_dirs)} extension folders.")
