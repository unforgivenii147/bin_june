#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


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

    clean_name = re_sub(r"(_\d+)+", "", path.name)
    return path.with_name(clean_name)


EXTENSIONS = {".js", ".css", ".html", ".json", ".mjs", ".cjs", ".ts", ".jsx", ".tsx"}
EXCLUDE_PATTERNS = {".py", ".ipynb"}


def should_format(file_path: Path) -> bool:
    return file_path.suffix in EXTENSIONS and not any(file_path.name.endswith(p) for p in EXCLUDE_PATTERNS)


def get_files_to_format(cwd: str = ".") -> list[Path]:
    return [p for p in Path(cwd).resolve().rglob("*") if p.is_file() and "error" not in p.parts and should_format(p)]


def format_file(file_path: Path) -> tuple[Path, bool, str | None]:
    try:
        result = subprocess.run(["prettier", "--write", str(file_path)], capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return file_path, True, None
        return file_path, False, result.stderr or "Unknown error"
    except Exception as e:
        return file_path, False, str(e)


def main() -> None:
    cwd = Path.cwd()
    files = get_files_to_format(cwd)
    if not files:
        print("ℹ️  No files found to format")
        return
    print(f"📁 Scanning: {cwd} | 📝 Found {len(files)} files")
    success_count = 0
    error_count = 0
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(format_file, f): f for f in files}
        for future in as_completed(futures):
            path, success, error_msg = future.result()
            if success:
                print(f"  ✅ Formatted: {path.name}")
                success_count += 1
            else:
                print(f"  ❌ Error: {path.name} -> {error_msg}")
                error_dir = path.parent / "error"
                error_dir.mkdir(exist_ok=True)
                dest = unique_path(error_dir / path.name)
                shutil.move(str(path), str(dest))
                error_count += 1
    print(f"\n✅ Success: {success_count} | ❌ Errors: {error_count}")


if __name__ == "__main__":
    main()
