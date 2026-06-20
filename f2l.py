#!/data/data/com.termux/files/usr/bin/python
import subprocess
import sys
from pathlib import Path


def main() -> None:
    fn = sys.argv[1]
    filepath = Path(fn)

    # Read and process in one pass
    with filepath.open(encoding="utf-8") as f:
        lines = [line.strip() for line in f]

    # Build formatted string
    items = []
    for line in lines:
        quote_char = "'" if '"' in line else '"'
        items.append(f"{quote_char}{line}{quote_char}")

    formatted_content = "{" + ", ".join(items) + "}"

    # Write in-place
    filepath.write_text(formatted_content, encoding="utf-8")

    # Copy to clipboard via pipe (more reliable)
    try:
        subprocess.run(["termux-clipboard-set"], input=formatted_content, text=True, capture_output=True)
        print(f"✓ Updated and copied: {filepath}")
    except FileNotFoundError:
        print(f"✓ File updated: {filepath}")
        print("⚠ Install termux-api for clipboard support")


if __name__ == "__main__":
    sys.exit(main())
