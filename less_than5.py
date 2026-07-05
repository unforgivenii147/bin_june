#!/data/data/com.termux/files/usr/bin/python
import os
import time
from pathlib import Path

TIME_THRESHOLD = 8 * 60


def get_file_age(filepath: str) -> float:
    current_time = time.time()
    file_stat = os.stat(filepath)
    file_creation_time = file_stat.st_ctime
    return current_time - file_creation_time


def move_recent_files(start_dir: (Path | str) = ".") -> None:
    target_dir = os.path.join(start_dir, "5min")
    Path(target_dir).mkdir(exist_ok=True, parents=True)
    moved_count = 0
    for root, dirs, files in os.walk(start_dir):
        if "5min" in dirs:
            dirs.remove("5min")
        for file in files:
            filepath = os.path.join(root, file)
            try:
                if get_file_age(filepath) <= TIME_THRESHOLD:
                    rel_path = os.path.relpath(root, start_dir)
                    if rel_path == ".":
                        dest_dir = target_dir
                    else:
                        dest_dir = os.path.join(target_dir, rel_path)
                        Path(dest_dir).mkdir(exist_ok=True, parents=True)
                    dest_path = os.path.join(dest_dir, file)
                    if Path(dest_path).exists():
                        base, ext = os.path.splitext(file)
                        counter = 1
                        while Path(dest_path).exists():
                            new_filename = f"{base}_{counter}{ext}"
                            dest_path = os.path.join(dest_dir, new_filename)
                            counter += 1
                    print(f"Moved: {filepath} -> {dest_path}")
                    moved_count += 1
            except (OSError, PermissionError) as e:
                print(f"Error processing {filepath}: {e}")
    print(f"\nTotal files moved: {moved_count}")


def main() -> None:
    try:
        start_dir = Path.cwd()
        print(f"Starting from directory: {start_dir}")
        print(f"Moving files created in last 5 minutes to '{os.path.join(start_dir, '5min')}'")
        print("-" * 60)
        move_recent_files(start_dir)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
