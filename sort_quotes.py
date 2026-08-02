#!/data/data/com.termux/files/home/.local/bin/python

import json
import os
import sys


def dedup_quotes(quotes):
    seen = set()
    unique = []
    for q in quotes:
        key = q["quote"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique


def sort_quotes(path, sort_by_key="quote"):
    if not os.path.exists(path):
        print(f"Error: '{path}' could not be found.")
        return
    with open(path, "r", encoding="utf-8") as f:
        try:
            quotes = json.load(f)
        except json.JSONDecodeError:
            print("Error: 'quotes.json' is empty or contains invalid formatting.")
            return
    uniques = dedup_quotes(quotes)
    uniques.sort(key=lambda item: item.get(sort_by_key, "").lower())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(uniques, f, indent=2, ensure_ascii=False)
    print(f"Success: Sorted")


def format_json(input_file):
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    output_lines = ["["]
    for i, record in enumerate(data):
        record_str = json.dumps(record, ensure_ascii=False)
        if i < len(data) - 1:
            record_str += ","
        output_lines.append(record_str)
    output_lines.append("]")
    with open(input_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
        f.write("\n")  # Add trailing newline


if __name__ == "__main__":
    fn = sys.argv[1]
    if "-a" in sys.argv:
        sort_by_key = "author"
    else:
        sort_by_key = "quote"
    sort_quotes(fn, sort_by_key=sort_by_key)
    format_json(fn)
