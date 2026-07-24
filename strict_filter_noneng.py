#!/data/data/com.termux/files/home/.local/bin/python
import argparse
import re
import sys
from pathlib import Path
import gcld3
import nltk

# Ensure the words corpus is downloaded locally
try:
    nltk.data.find("corpora/words")
except LookupError:
    nltk.download("words", quiet=True)

from nltk.corpus import words


def is_english_strict(line: str, detector, english_vocab: set, min_ratio: float = 0.5) -> tuple[bool, str]:
    """
    Stricter verification: Combines gcld3 predictions with NLTK dictionary lookups.
    Returns (is_english, metadata_string).
    """
    clean_line = line.strip()
    if not clean_line:
        return True, "Empty"

    # Step 1: Query Google CLD3 Neural Detector
    result = detector.FindLanguage(clean_line)
    cld3_is_en = result.language == "en" and result.is_reliable

    # Step 2: Tokenize and verify with NLTK words
    # Extracts all individual alphanumeric sequences, forcing lowercase
    tokens = re.findall(r"\b[a-zA-Z]+\b", clean_line.lower())

    # If the line contains no alphabetic tokens (e.g., pure numbers/symbols), trust CLD3
    if not tokens:
        return cld3_is_en, f"CLD3:{result.language.upper()}(No Words)"

    # Count how many tokens exist in the NLTK English dataset
    matched_words = sum(1 for token in tokens if token in english_vocab)
    nltk_ratio = matched_words / len(tokens)

    # Step 3: Enforce strict hybrid logic
    # To be classified as English, it must pass the neural model AND cross the dictionary density barrier
    if cld3_is_en and nltk_ratio >= min_ratio:
        return True, "EN"

    # Formulate structural log tags for non-English outputs
    reason = f"NLTK Ratio: {nltk_ratio:.2f}"
    if result.language != "en":
        reason += f" | CLD3: {result.language.upper()}"
    return False, reason


def process_file_lines(input_path: Path, move_mode: bool, strict_ratio: float):
    if not input_path.is_file():
        print(f"❌ Error: The file '{input_path}' does not exist.")
        sys.exit(1)

    detector = gcld3.NNetLanguageIdentifier(min_num_bytes=0, max_num_bytes=1000)

    # Load NLTK words into a hashed set for O(1) lightning-fast lookups
    print("🧠 Loading NLTK English vocabulary corpus...")
    english_vocab = set(w.lower() for w in words.words())

    try:
        lines = input_path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)

    english_lines = []
    non_english_lines = []

    print(f"🔍 Strictly scanning {len(lines)} lines from '{input_path.name}'...")
    print("-" * 70)

    for i, line in enumerate(lines, start=1):
        is_en, diagnostic = is_english_strict(line, detector, english_vocab, strict_ratio)

        if is_en:
            english_lines.append(line)
        else:
            non_english_lines.append(line)
            print(f"Line {i} [{diagnostic}]: {line.strip()}")

    print("-" * 70)
    print(f"📊 Strict Filter Summary: Identified {len(non_english_lines)} non-English lines.")

    if move_mode:
        if not non_english_lines:
            print("ℹ️  No non-English lines crossed the strict detection threshold.")
            return

        output_path = Path("noneng.txt")
        try:
            output_path.write_text("\n".join(non_english_lines) + "\n", encoding="utf-8")
            print(f"💾 Extracted text written safely to: {output_path.resolve()}")

            input_path.write_text("\n".join(english_lines) + "\n", encoding="utf-8")
            print(f"🔄 In-place clean file written back to original location.")
        except Exception as e:
            print(f"❌ Storage error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Filter non-English lines strictly using a hybrid GCLD3 and NLTK dictionary method."
    )
    parser.add_argument("file", type=str, help="The text file to scan.")
    parser.add_argument(
        "-m",
        "--move",
        action="store_true",
        help="Isolate non-English lines into noneng.txt and update source in-place.",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=0.50,
        help="Minimum ratio (0.0 to 1.0) of tokens that must be valid NLTK English words (default: 0.50).",
    )

    args = parser.parse_args()
    process_file_lines(Path(args.file), args.move, args.threshold)


if __name__ == "__main__":
    main()
