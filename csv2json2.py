#!/data/data/com.termux/files/usr/bin/env python


import csv
import json
import sys
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python csv_to_json.py <input.csv>")
        sys.exit(1)
    input_path = Path(sys.argv[1])
    output_path = input_path.with_suffix(".json")
    with open(input_path, mode="r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        data = [row for row in reader]
    with open(output_path, mode="w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
