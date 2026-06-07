#!/data/data/com.termux/files/usr/bin/python

import os
import sys
from datetime import datetime
from pathlib import Path


def get_file_creation_time(filepath):
    try:
        stat = os.stat(filepath)
        if sys.platform == "win32":
            return datetime.fromtimestamp(stat.st_ctime)
        return datetime.fromtimestamp(stat.st_mtime)
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <filename>")
        sys.exit(1)
    filename = sys.argv[1]
    if not Path(filename).exists():
        print(f"Error: File '{filename}' does not exist.")
        sys.exit(1)
    directory = Path(filename).parent or "."
    target_time = get_file_creation_time(filename)
    if not target_time:
        sys.exit(1)
    target_date = target_time.date()
    print(f"Input file: {filename}")
    print(f"Created on: {target_date}")
    print("-" * 50)
    found_files = []
    for file in os.listdir(directory):
        filepath = os.path.join(directory, file)
        if not Path(filepath).is_file() or Path(filepath).samefile(filename):
            continue
        file_time = get_file_creation_time(filepath)
        if file_time and file_time.date() == target_date:
            found_files.append((file_time, file))
    found_files.sort()
    if not found_files:
        print("No other files found created on the same day.")
    else:
        print(f"Found {len(found_files)} other file(s) created on the same day:")
        for file_time, file in found_files:
            print(f"{file_time.strftime('%H:%M:%S')} - {file}")


if __name__ == "__main__":
    main()
