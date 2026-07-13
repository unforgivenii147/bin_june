#!/data/data/com.termux/files/usr/bin/env python
"""
Offline Persian \u2194 English translator.
Optimized for Python 3.12.
"""

import argparse
import json
import logging
import readline
import sys
from collections.abc import Iterable
from difflib import get_close_matches
from pathlib import Path
from typing import Final

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Configuration
DICT_FILE: Final[str] = "/sdcard/isaac/dic.json"


def load_dictionary(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Loads and parses the translation dictionary."""
    if not path.exists():
        logger.error("Error: Dictionary file %s not found", path)
        sys.exit(1)

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        fa_en = {str(k).strip(): str(v).strip() for k, v in data.items()}
        en_fa = {v: k for k, v in fa_en.items()}
        return fa_en, en_fa
    except Exception as e:
        logger.error("Error loading dictionary: %s", e)
        sys.exit(1)


def setup_readline(words: Iterable[str]) -> None:
    """Configures readline for tab completion."""
    sorted_words = sorted(words)

    def completer(text: str, state: int) -> str | None:
        matches = [w for w in sorted_words if w.startswith(text)]
        return matches[state] if state < len(matches) else None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t\n")


def translate(word: str, fa_en: dict[str, str], en_fa: dict[str, str]) -> str | None:
    """Translates a word in either direction."""
    return fa_en.get(word) or en_fa.get(word)


def fuzzy_search(word: str, all_words: set[str], limit: int = 5, cutoff: float = 0.6) -> list[str]:
    """Performs fuzzy matching for typo tolerance."""
    return get_close_matches(word, all_words, n=limit, cutoff=cutoff)


def interactive_mode(fa_en: dict[str, str], en_fa: dict[str, str]) -> None:
    """Runs a REPL for translations."""
    all_words = set(fa_en) | set(en_fa)
    setup_readline(all_words)

    print("\n\U0001f310 Offline Persian \u2194 English Translator")
    print("\u2328  TAB for suggestions, Ctrl+C to exit\n")

    while True:
        try:
            word = input("> ").strip()
            if not word:
                continue

            result = translate(word, fa_en, en_fa)
            if result:
                print(f"\u2705 {result}")
            else:
                matches = fuzzy_search(word, all_words)
                if matches:
                    print(f"\u2753 Not found. Did you mean: {', '.join(matches)}?")
                else:
                    print("\u274c Not found")

        except (KeyboardInterrupt, EOFError):
            print("\n\U0001f44b Bye.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Persian \u2194 English translator")
    parser.add_argument("word", nargs="*", help="Word to translate")
    parser.add_argument("--prefix", help="List words starting with prefix")
    parser.add_argument("--fuzzy", help="Fuzzy search (typo tolerant)")
    args = parser.parse_args()

    fa_en, en_fa = load_dictionary(Path(DICT_FILE))
    all_words = set(fa_en) | set(en_fa)

    if args.prefix:
        matches = sorted(w for w in all_words if w.startswith(args.prefix))
        if matches:
            print("\n".join(matches))
            sys.exit(0)
        logger.info("No matches found for prefix: %s", args.prefix)
        sys.exit(1)

    if args.fuzzy:
        matches = fuzzy_search(args.fuzzy, all_words)
        if matches:
            print("\n".join(matches))
            sys.exit(0)
        logger.info("No close matches found for: %s", args.fuzzy)
        sys.exit(1)

    if args.word:
        word = " ".join(args.word).strip()
        result = translate(word, fa_en, en_fa)
        if result:
            print(result)
            sys.exit(0)
        else:
            matches = fuzzy_search(word, all_words)
            if matches:
                print(f"Not found. Did you mean: {', '.join(matches)}?", file=sys.stderr)
            else:
                print("Not found", file=sys.stderr)
            sys.exit(1)

    interactive_mode(fa_en, en_fa)


if __name__ == "__main__":
    main()
