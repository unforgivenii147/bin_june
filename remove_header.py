#!/data/data/com.termux/files/usr/bin/python
import sys
import json


def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <json_file>")
        sys.exit(1)

    fn = sys.argv[1]

    with open(fn, "r", encoding="utf-8") as f:
        data = json.load(f)

    transformed = []
    for item in data:
        # Extract all values from the item, ignoring the keys
        values = list(item.values())
        if len(values) >= 2:
            # Create a new dict with the values as key-value pairs using generic names
            # Or just keep the values as a list
            transformed.append({f"field_{i + 1}": value for i, value in enumerate(values)})
        else:
            # If less than 2 fields, just keep as is
            transformed.append(item)

    with open(fn, "w", encoding="utf-8") as fo:
        json.dump(transformed, fo, ensure_ascii=False, indent=2)

    print(f"Successfully transformed {fn}")


if __name__ == "__main__":
    main()
