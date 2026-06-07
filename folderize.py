#!/data/data/com.termux/files/usr/bin/python

import os
import shutil
from pathlib import Path


def falpha(cwd="."):
    root_path = Path(cwd).resolve()
    all_files = [f for f in root_path.rglob("*") if f.is_file()]
    for file_path in all_files:
        if is_in_alphabetical_folder(file_path, root_path):
            continue
        first_char = file_path.name[0].upper()
        if first_char.isalpha():
            folder_name = first_char
        elif first_char.isdigit():
            folder_name = "0-9"
        else:
            folder_name = "Other"
        dest_folder = root_path / folder_name
        dest_folder.mkdir(exist_ok=True)
        dest_path = dest_folder / file_path.name
        final_dest = get_unique_filename(dest_path)
        try:
            shutil.move(str(file_path), str(final_dest))
            print(f"Moved: {file_path.name} -> {final_dest}")
        except Exception as e:
            print(f"Error moving {file_path.name}: {e}")


def is_in_alphabetical_folder(file_path, root_path):
    relative_path = file_path.relative_to(root_path)
    if len(relative_path.parts) > 1:
        parent_folder = relative_path.parts[0]
        if len(parent_folder) == 1 and parent_folder.isalpha() or parent_folder in {"0-9", "Other"}:
            return True
    return False


def get_unique_filename(dest_path):
    if not dest_path.exists():
        return dest_path
    stem = dest_path.stem
    suffix = dest_path.suffix
    parent = dest_path.parent
    index = 1
    while True:
        new_name = f"{stem}({index}){suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        index += 1


if __name__ == "__main__":
    falpha(".")
    for k in os.listdir("."):
        print(k)
