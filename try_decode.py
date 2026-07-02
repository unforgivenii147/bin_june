#!/data/data/com.termux/files/usr/bin/env python
"""
File Encoding Decoder Tool
Attempts to decode a file using various encodings and saves as UTF-8
"""

import os
import sys
import codecs
from pathlib import Path

# Common encodings to try (ordered by likelihood)
COMMON_ENCODINGS = [
    "utf-8",
    "utf-8-sig",  # UTF-8 with BOM
    "latin-1",  # ISO-8859-1
    "cp1252",  # Windows Western European
    "cp1251",  # Windows Cyrillic
    "cp1256",  # Windows Arabic
    "iso-8859-1",  # Western European
    "iso-8859-2",  # Central European
    "iso-8859-5",  # Cyrillic
    "iso-8859-6",  # Arabic
    "iso-8859-7",  # Greek
    "iso-8859-8",  # Hebrew
    "iso-8859-9",  # Turkish
    "cp437",  # DOS Latin US
    "cp850",  # DOS Latin 1
    "cp866",  # DOS Cyrillic
    "mac_roman",  # Mac Roman
    "utf-16",  # UTF-16 (with BOM)
    "utf-16-le",  # UTF-16 Little Endian
    "utf-16-be",  # UTF-16 Big Endian
    "utf-32",  # UTF-32 (with BOM)
    "utf-32-le",  # UTF-32 Little Endian
    "utf-32-be",  # UTF-32 Big Endian
    "gbk",  # Chinese Simplified
    "gb2312",  # Chinese Simplified
    "big5",  # Chinese Traditional
    "shift_jis",  # Japanese
    "euc_jp",  # Japanese
    "euc_kr",  # Korean
]

# Additional less common encodings
EXTRA_ENCODINGS = [
    "ascii",
    "cp775",  # Baltic
    "cp852",  # Central European DOS
    "cp855",  # Cyrillic DOS
    "cp857",  # Turkish DOS
    "cp860",  # Portuguese DOS
    "cp861",  # Icelandic DOS
    "cp862",  # Hebrew DOS
    "cp863",  # Canadian French DOS
    "cp865",  # Nordic DOS
    "cp869",  # Greek DOS
    "cp874",  # Thai
    "cp949",  # Korean
    "cp950",  # Chinese Traditional
    "koi8_r",  # Russian
    "koi8_u",  # Ukrainian
    "mac_cyrillic",
    "mac_greek",
    "mac_iceland",
    "mac_latin2",
]


def try_decode(file_content: bytes, encoding: str):
    """Attempt to decode bytes using the specified encoding"""
    try:
        decoded = file_content.decode(encoding)
        return True, decoded
    except (UnicodeDecodeError, LookupError):
        return False, None


def get_first_chunk(text: str, chunk_size: int = 500) -> str:
    """Get first chunk of text with ellipsis if longer"""
    if len(text) <= chunk_size:
        return text
    return text[:chunk_size] + "...\n[truncated...]"


def decode_file(file_path: str, output_path: str = None, show_chunk: int = 500):
    """
    Try to decode a file with various encodings and save as UTF-8

    Args:
        file_path: Path to input file
        output_path: Path for output file (default: input_file_utf8.txt)
        show_chunk: Number of characters to show for each successful decode (0 to disable)
    """
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"Error: File '{file_path}' not found.")
        return False

    # Read raw bytes
    try:
        with open(file_path, "rb") as f:
            file_content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

    print(f"Processing: {file_path.name}")
    print(f"File size: {len(file_content)} bytes")
    print("-" * 60)

    # Try common encodings first
    encodings_to_try = COMMON_ENCODINGS + EXTRA_ENCODINGS
    successful_encodings = []
    successful_text = None
    best_encoding = None

    for encoding in encodings_to_try:
        success, decoded_text = try_decode(file_content, encoding)
        if success:
            successful_encodings.append(encoding)
            if successful_text is None:
                successful_text = decoded_text
                best_encoding = encoding

            print(f"✓ {encoding:15} - Successfully decoded!")
            if show_chunk > 0:
                chunk = get_first_chunk(decoded_text, show_chunk)
                # Print chunk with indentation and escaping problematic characters
                preview = chunk.replace("\n", "\n  ").replace("\r", "\\r")
                print(f"  Preview:\n  {preview}\n")

    print("-" * 60)

    if not successful_encodings:
        print("❌ No encoding could decode this file.")
        return False

    print(f"\n✅ Found {len(successful_encodings)} successful encoding(s):")
    for enc in successful_encodings:
        print(f"  - {enc}")

    print(f"\n📌 Best match: {best_encoding}")

    # Ask user to choose encoding if multiple found
    if len(successful_encodings) > 1:
        print("\nMultiple encodings found. Which one should be used for UTF-8 conversion?")
        print("0: Cancel")
        for i, enc in enumerate(successful_encodings, 1):
            print(f"{i}: {enc}")

        try:
            choice = input(f"Enter choice (1-{len(successful_encodings)}): ").strip()
            if not choice:
                choice = "1"
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(successful_encodings):
                chosen_encoding = successful_encodings[choice_idx]
            else:
                print("Invalid choice. Using best match.")
                chosen_encoding = best_encoding
        except ValueError:
            print("Invalid input. Using best match.")
            chosen_encoding = best_encoding
    else:
        chosen_encoding = best_encoding

    # Re-decode with chosen encoding and save as UTF-8
    try:
        decoded_text = file_content.decode(chosen_encoding)
    except Exception as e:
        print(f"Error decoding with {chosen_encoding}: {e}")
        return False

    # Generate output filename
    if output_path is None:
        output_path = file_path.stem + "_utf8" + file_path.suffix
        if file_path.suffix.lower() == ".txt":
            output_path = file_path.stem + "_utf8.txt"
        else:
            output_path = file_path.parent / f"{file_path.stem}_utf8{file_path.suffix}"

    # Save as UTF-8
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(decoded_text)
        print(f"\n💾 Saved UTF-8 version to: {output_path}")
        print(f"   Original encoding: {chosen_encoding}")
        print(f"   Characters decoded: {len(decoded_text)}")
        return True
    except Exception as e:
        print(f"Error saving file: {e}")
        return False


def main():
    """Main entry point with command-line arguments"""
    if len(sys.argv) < 2:
        print("Usage: python decode_file.py <file_path> [output_path]")
        print("Example: python decode_file.py mystery.txt")
        print("Example: python decode_file.py mystery.txt decoded.txt")
        sys.exit(1)

    file_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    decode_file(file_path, output_path)


if __name__ == "__main__":
    main()
