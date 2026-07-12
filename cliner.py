#!/data/data/com.termux/files/usr/bin/env python


import mmap
import re
from collections.abc import Callable, Iterable
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


LOG_EXT = ".log"
MMAP_THRESHOLD = 1 * 1024 * 1024
NUM_WORKERS = 4
PATTERNS = [
    "\\^\\[",
    "\\[[\\dA-Z;]+m",
    "\\[\\d+[A-Z]",
    "\\[[\\dA-Z;]+",
    "\\^M",
    "\\(B",
    "\\(0",
    "\\x1b\\[[0-9;]*[A-Za-z]",
    "\\x1b\\([0-9AB]",
    "\\r",
    "\\x0f",
    "\\x0e",
]
COMPILED_PATTERNS = [re.compile(pattern) for pattern in PATTERNS]


def clean_line(line: str) -> str:
    cleaned = line
    for pattern in COMPILED_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return re.sub(r" {2,}", " ", cleaned)


def clean_file_small(path: Path) -> tuple:
    try:
        with path.open(encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        cleaned_lines = [clean_line(line) for line in lines]
        with path.open("w", encoding="utf-8") as f:
            f.writelines(cleaned_lines)
        return path, True, "small file"
    except Exception as e:
        return path, False, str(e)


def clean_file_large(path: Path) -> tuple:
    try:
        with path.open("r+b") as f:
            get_size = f.seek(0, 2)
            f.seek(0)
            if get_size == 0:
                return path, True, "empty file"
            with mmap.mmap(f.fileno(), 0) as mmapped_file:
                content = mmapped_file.read().decode("utf-8", errors="ignore")
        lines = content.splitlines(keepends=True)
        cleaned_lines = [clean_line(line) for line in lines]
        cleaned_content = "".join(cleaned_lines)
        Path(path).write_text(cleaned_content, encoding="utf-8")
        return path, True, "large file (mmap)"
    except Exception as e:
        return path, False, str(e)


def clean_file_worker(path: Path) -> tuple:
    try:
        get_size = path.stat().st_size
        if get_size > MMAP_THRESHOLD:
            return clean_file_large(path)
        return clean_file_small(path)
    except Exception as e:
        return path, False, str(e)


def main() -> None:
    cwd = Path.cwd()
    log_files = list(cwd.rglob(f"*{LOG_EXT}"))
    if not log_files:
        print(f"No {LOG_EXT} files found.")
        return
    print(f"Found {len(log_files)} log file(s).")
    results = mpf3(clean_file_worker, log_files)
    success_count = 0
    error_count = 0
    for path, success, message in results:
        if success:
            print(f"✓ Cleaned: {path} ({message})")
            success_count += 1
        else:
            print(f"✗ Error: {path} - {message}")
            error_count += 1
    print(f"\nDone. Successfully processed {success_count}/{len(log_files)} file(s).")
    if error_count > 0:
        print(f"Failed: {error_count} file(s).")


if __name__ == "__main__":
    main()
