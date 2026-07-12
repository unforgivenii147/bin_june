#!/data/data/com.termux/files/usr/bin/env python


import json
import operator
from os import scandir as os_scandir
from pathlib import Path

import ssdeep

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def calculate_ssdeep_hash(filepath: Path, min_file_size: int = 1):
    try:
        if filepath.stat().st_size < min_file_size:
            return None
        with filepath.open("rb") as f:
            data = f.read()
            if len(data) < min_file_size:
                return None
            return ssdeep.hash(data)
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None
    except OSError as e:
        print(f"OS error accessing {filepath}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred for {filepath}: {e}")
        return None


def compare_files(file_paths: list[Path], similarity_threshold: int = 70):
    file_hashes = {}
    for filepath in file_paths:
        file_hash = calculate_ssdeep_hash(filepath)
        if file_hash:
            file_hashes[str(filepath)] = file_hash
    similarities = []
    cwd = Path.cwd()
    filepaths_list = list(file_hashes.keys())
    for i in range(len(filepaths_list)):
        for j in range(i + 1, len(filepaths_list)):
            filepath1_str = filepaths_list[i]
            filepath2_str = filepaths_list[j]
            hash1 = file_hashes[filepath1_str]
            hash2 = file_hashes[filepath2_str]
            try:
                score = ssdeep.compare(hash1, hash2)
                if score >= similarity_threshold:
                    similarities.append({
                        "file1": str(Path(filepath1_str).relative_to(cwd)),
                        "file2": str(Path(filepath2_str).relative_to(cwd)),
                        "similarity_score": score,
                    })
            except ssdeep.error as e:
                print(f"Error comparing hashes for {filepath1_str} and {filepath2_str}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred during comparison for {filepath1_str} and {filepath2_str}: {e}")
    similarities.sort(key=operator.itemgetter("similarity_score"), reverse=True)
    return similarities


def save_to_json(data, filename: str = "simz.json") -> None:
    try:
        with Path(filename).open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving data to JSON file '{filename}': {e}")


if __name__ == "__main__":
    cwd = Path.cwd()
    MIN_SIMILARITY_THRESHOLD = 30
    OUTPUT_JSON_FILE = "simz.json"
    files = get_files(cwd)
    if not files:
        print("No files found matching the criteria in the specified directory.")
    else:
        similar_file_pairs = compare_files(files, MIN_SIMILARITY_THRESHOLD)
        if similar_file_pairs:
            save_to_json(similar_file_pairs, OUTPUT_JSON_FILE)
        else:
            print(f"\nNo files found with similarity >= {MIN_SIMILARITY_THRESHOLD}%.")
