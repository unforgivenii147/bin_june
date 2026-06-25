#!/data/data/com.termux/files/usr/bin/python

import json
import sys
from pathlib import Path


def file_to_json(filepath: Path, delimiter: str):
    result = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(delimiter, 1)
                if len(parts) != 2:
                    print(
                        f"Warning: Line {line_num} doesn't contain delimiter '{delimiter}': {line!r}",
                        file=sys.stderr,
                    )
                    continue
                key, value = parts
                key = key.strip()
                value = value.lstrip().strip()
                result.setdefault(key, []).append(value)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <filename> <delimiter>", file=sys.stderr)
        sys.exit(1)
    filename = Path(sys.argv[1])
    delimiter = sys.argv[2]
    result = file_to_json(filename, delimiter)
    jsonfile = filename.with_suffix(".json")
    with jsonfile.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
