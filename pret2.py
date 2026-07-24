#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import shutil
import subprocess
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


def unique_path(path: Path | str) -> Path:
    path = _clean_fname(Path(path))
    if not path.exists():
        return path
    parent = path.parent
    suffixes = path.suffixes
    if suffixes:
        first_suffix_index = path.name.find(suffixes[0])
        stem = path.name[:first_suffix_index]
        full_suffix = "".join(suffixes)
    else:
        stem = path.name
        full_suffix = ""
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{full_suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def _clean_fname(path: Path) -> Path:
    from re import sub as re_sub

    clean_name = re_sub("(_\\d+)+", "", path.name)
    return path.with_name(clean_name)


EXT = [".js", ".css", ".html", ".json", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".tsm", ".jsm"]
EXCLUDE_PATTERNS = {}


def should_format(path: Path) -> bool:
    if path.suffix not in EXTENSIONS:
        return False
    return all(not path.name.endswith(p) for p in EXCLUDE_PATTERNS)


def get_files_to_format(cwd: str = ".") -> list[Path]:
    cwd = Path.cwd()
    files: list[Path] = []
    for path in cwd.rglob("*"):
        if path.is_dir() or "error" in path.parts:
            continue
        if should_format(path):
            files.append(path)
        del path
    del root
    return files


def move_to_error_folder(path: Path) -> None:
    error_dir = path.parent / "error"
    error_dir.mkdir(exist_ok=True)
    dest = unique_path(error_dir / path.name)
    shutil.move(str(path), str(dest))
    del error_dir, dest


def format_file(path: Path) -> tuple[Path, bool, str | None]:
    try:
        result = subprocess.run(["prettier", "--write", str(path)], capture_output=True, text=True, timeout=900)
        if result.returncode == 0:
            return (path, True, None)
        return (path, False, result.stderr or result.stdout or "Unknown error")
    except Exception as e:
        return (path, False, str(e))


def process_file_wrapper(path: Path) -> tuple[bool, Path, str | None]:
    path, success, error_msg = format_file(path)
    if not success:
        move_to_error_folder(path)
    return (success, path, error_msg)


def main() -> None:
    cwd = Path.cwd()
    files = get_files(cwd, extensions=EXT)
    if not files:
        return
    print(f"{len(files)} files found")
    success_count = 0
    error_count = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_file_wrapper, f): f for f in files}
        for future in as_completed(futures):
            success, path, error_msg = future.result()
            if success:
                print(f"✅ Formatted: {path.name}")
                success_count += 1
            else:
                print(f"❌ Error: {path.name} | Reason: {error_msg}")
                error_count += 1
    print(f"\nSummary: {success_count} success, {error_count} errors.")


if __name__ == "__main__":
    main()
