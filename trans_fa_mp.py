#!/data/data/com.termux/files/usr/bin/python

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from deep_translator import GoogleTranslator

INPUT_FILE = "words.txt"
OUTPUT_FILE = "dic_mp.json"
MAX_WORKERS = 16


def translate_word(word) -> str | None:
    for attempt in range(3):
        try:
            return GoogleTranslator(source="auto", target="en").translate(word)
        except Exception as e:
            print(f"[WARN] Failed '{word}' (attempt {attempt + 1}): {e}")
            time.sleep(0.5)
    return None


def main() -> None:
    with Path(INPUT_FILE).open(encoding="utf-8") as f:
        words = [w.strip() for w in f if w.strip()]
    print(f"[INFO] Loaded {len(words)} Persian words")
    results = {}
    print("[INFO] Translating in parallel...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(translate_word, w): w for w in words}
        for future in as_completed(future_map):
            persian_word = future_map[future]
            try:
                english = future.result()
                if english:
                    results[persian_word] = english
                    print(f"{persian_word} → {english}")
                else:
                    print(f"[FAIL] Could not translate: {persian_word}")
            except Exception as e:
                print(f"[ERROR] Unexpected error for '{persian_word}': {e}")
    with Path(OUTPUT_FILE).open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[SAVED] Translation dictionary saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
