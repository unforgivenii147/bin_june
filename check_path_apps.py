#!/data/data/com.termux/files/usr/bin/python

import os
from collections import defaultdict
from pathlib import Path


def find_path_duplicates():
    path_env = os.environ.get("PATH", "")
    directories = [d for d in path_env.split(":") if d]
    app_map = defaultdict(list)
    print(f"--- Scanning {len(directories)} directories in PATH ---\n")
    for directory in directories:
        if not Path(directory).is_dir():
            continue
        try:
            for item in os.listdir(directory):
                full_path = os.path.join(directory, item)
                if Path(full_path).is_file() and os.access(full_path, os.X_OK):
                    app_map[item].append(directory)
        except PermissionError:
            print(f"Permission denied: {directory}")
            continue
    duplicates_found = False
    for app, locations in app_map.items():
        if len(locations) > 1:
            duplicates_found = True
            print(f"Duplicate found: [ {app} ]")
            for i, loc in enumerate(locations):
                status = " (ACTIVE)" if i == 0 else " (SHADOWED)"
                print(f"  - {loc}{status}")
            print("-" * 30)
    if not duplicates_found:
        print("Clean as a whistle! No duplicate executables found.")


if __name__ == "__main__":
    find_path_duplicates()
