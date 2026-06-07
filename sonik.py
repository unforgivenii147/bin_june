#!/data/data/com.termux/files/usr/bin/python

import os
import sys


def sort_and_dedup(file_name):
    file_size = os.path.getsize(file_name)
    with open(file_name) as f:
        lines = f.readlines()
    unique_lines = sorted(set(lines))
    removed_lines = set(lines) - set(unique_lines)
    with open(file_name, "w") as f:
        f.writelines(unique_lines)
    print(f"Removed {len(removed_lines)} lines.")
    print("Removed lines:")
    for line in sorted(set(removed_lines)):
        print(line.strip())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sort_uniq.py <file_name> [-d]")
        sys.exit(1)
    file_name = sys.argv[1]
    sort_and_dedup(file_name)
