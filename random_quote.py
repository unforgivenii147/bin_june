#!/data/data/com.termux/files/usr/bin/env python


import json
import random

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def show_random_quote():
    try:
        with open("/sdcard/data/quotes.json", "r", encoding="utf-8") as f:
            quotes = json.load(f)
        if not quotes:
            print("No quotes found in the file.")
            return
        quote = random.choice(quotes)
        print("\n" + "=" * 60)
        print(f'''"{quote["quote"]}"''')
        print(f"  — {quote['author']}")
        print("=" * 60 + "\n")
    except FileNotFoundError:
        print("Error: quotes.json not found at /sdcard/data/quotes.json")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format in quotes.json")
    except KeyError:
        print("Error: Quote or author field missing in JSON")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    show_random_quote()
