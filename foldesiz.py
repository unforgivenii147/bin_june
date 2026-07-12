#!/data/data/com.termux/files/usr/bin/env python
import operator
import os
import shutil
import sys
from pathlib import Path


from pathlib import Path


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


def should_skip(path: (str | Path)) -> bool:
    path = Path(path)
    return bool(path.is_symlink() or not SKIP_DIRS.isdisjoint(path.parts))


def get_all_files(cwd: Path):
    files = []
    for path in cwd.rglob("*"):
        if should_skip(path):
            continue
        if path.is_file():
            size = path.stat().st_size
            files.append((path, size))
    return sorted(files, key=operator.itemgetter(1))


def get_num_folders(files) -> int:
    if len(files) < 2:
        return 1
    sizes = [size for _, size in files]
    max_size, min_size = max(sizes), min(sizes)
    range_size = max_size - min_size
    target_range_per_folder = range_size / 100
    num_folders = max(1, int(range_size / target_range_per_folder))
    return min(num_folders, len(files))


def create_range_folders(cwd: Path, files, num_folders: int):
    sizes = sorted([size for _, size in files])
    folder_ranges = []
    files_per_folder = len(files) // num_folders
    remainder = len(files) % num_folders
    start_idx = 0
    for i in range(num_folders):
        end_idx = start_idx + files_per_folder + (1 if i < remainder else 0)
        folder_files = sizes[start_idx:end_idx]
        if folder_files:
            min_size, max_size = min(folder_files), max(folder_files)

            def fsz(size) -> str:
                if size < 1000:
                    return f"{size}B"
                if size < 1000000:
                    return f"{size // 1000}k"
                if size < 1000000000:
                    return f"{size // 1000000}M"
                return f"{size // 1000000000}G"

            folder_name = f"{fsz(min_size)}-{fsz(max_size)}"
            folder_ranges.append((min_size, max_size, folder_name))
            folder_path = os.path.join(cwd, folder_name)
            Path(folder_path).mkdir(exist_ok=True, parents=True)
        start_idx = end_idx
    return folder_ranges


def distribute_files(files, folders, cwd: Path) -> None:
    size_to_folder = {}
    for min_size, max_size, folder_name in folders:
        size_to_folder[min_size, max_size] = folder_name
    moved_count = 0
    for filepath, size in files:
        for (min_size, max_size), folder_name in size_to_folder.items():
            if min_size <= size <= max_size:
                dest_folder = os.path.join(cwd, folder_name)
                dest_path = os.path.join(dest_folder, Path(filepath).name)
                try:
                    dest_path = unique_path(dest_path)
                    shutil.move(filepath, dest_path)
                    moved_count += 1
                    break
                except Exception as e:
                    print(f"Failed to move {filepath}: {e}")
                break
        else:
            print(f"No folder match for {Path(filepath).name} ({size:,} bytes)")


def main() -> None:
    cwd = Path.cwd()
    files = get_all_files(cwd)
    if not files:
        print("No files found.")
        return
    num_folders = int(sys.argv[1]) if len(sys.argv) > 0 else get_num_folders(files)
    print(f"{num_folders} dirs will be created")
    folders = create_range_folders(cwd, files, num_folders)
    distribute_files(files, folders, cwd)
    print("Folderization complete!")


if __name__ == "__main__":
    main()
