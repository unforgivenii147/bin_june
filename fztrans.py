#!/data/data/com.termux/files/usr/bin/python


import argparse
import json
import readline
import subprocess
import sys
from difflib import get_close_matches
from pathlib import Path

DICT_FILE = "/sdcard/isaac/dic.json"


def load_dictionary(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    fa_en = {str(k).strip(): str(v).strip() for k, v in data.items()}
    en_fa = {v: k for k, v in fa_en.items()}
    return fa_en, en_fa


def setup_readline(words) -> None:
    words = sorted(words)

    def completer(text, state):
        matches = [w for w in words if w.startswith(text)]
        return matches[state] if state < len(matches) else None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t\n")


def translate(word: str, fa_en: dict[str, str], en_fa: dict[str, str]):
    if word in fa_en:
        return fa_en[word]
    if word in en_fa:
        return en_fa[word]
    return None


def prefix_search(prefix, all_words: set[str]):
    return sorted(w for w in all_words if w.startswith(prefix))


def fuzzy_search(word, all_words: set[str], limit=5, cutoff=0.6):
    return get_close_matches(word, all_words, n=limit, cutoff=cutoff)


def fzf_select(all_words: set[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["fzf", "--prompt=Select word: "],
            check=False,
            input="\n".join(sorted(all_words)),
            text=True,
            stdout=subprocess.PIPE,
        )
    except FileNotFoundError:
        print("fzf not found in PATH", file=sys.stderr)
        sys.exit(1)
    selection = proc.stdout.strip()
    return selection or None


def interactive_mode(fa_en: dict[str, str], en_fa: dict[str, str]) -> None:
    all_words = set(fa_en) | set(en_fa)
    setup_readline(all_words)
    print("Offline Persian ↔ English Translator")
    print("TAB for suggestions, Ctrl+C to exit\n")
    while True:
        try:
            word = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break
        if not word:
            continue
        result = translate(word, fa_en, en_fa)
        print(result or "Not found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Persian ↔ English translator")
    parser.add_argument("word", nargs="*", help="Word to translate")
    parser.add_argument("--prefix", help="List words starting with prefix")
    parser.add_argument("--fuzzy", help="Fuzzy search (typo tolerant)")
    parser.add_argument("--fzf", default=True, action="store_true", help="Interactive fzf selector")
    args = parser.parse_args()
    fa_en, en_fa = load_dictionary(Path(DICT_FILE))
    all_words = set(fa_en) | set(en_fa)
    if args.fzf:
        selected = fzf_select(all_words)
        if not selected:
            sys.exit(0)
        result = translate(selected, fa_en, en_fa)
        if result:
            print(result)
            sys.exit(0)
        print("Not found", file=sys.stderr)
        sys.exit(1)
    if args.prefix:
        matches = prefix_search(args.prefix, all_words)
        if matches:
            print("\n".join(matches))
            sys.exit(0)
        print("No matches", file=sys.stderr)
        sys.exit(1)
    if args.fuzzy:
        matches = fuzzy_search(args.fuzzy, all_words)
        if matches:
            print("\n".join(matches))
            sys.exit(0)
        print("No close matches", file=sys.stderr)
        sys.exit(1)
    if args.word:
        word = " ".join(args.word).strip()
        result = translate(word, fa_en, en_fa)
        if result:
            print(result)
            sys.exit(0)
        print("Not found", file=sys.stderr)
        sys.exit(1)
    interactive_mode(fa_en, en_fa)


if __name__ == "__main__":
    main()
