#!/data/data/com.termux/files/home/.local/bin/python
import json
import os
import random
from shutil import get_terminal_size
# Adjust this path if the script is stored somewhere separate from your JSON file
FILE_NAME = "/sdcard/data/quotes/quotes.json"
def display_random_quote():
    if not os.path.exists(FILE_NAME):
        return
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        try:
            quotes = json.load(f)
        except json.JSONDecodeError:
            return
    if not quotes:
        return
    # Select one quote object completely at random
    selected = random.choice(quotes)
    quote_text = selected.get("quote", "No quote content.")
    author_text = selected.get("author", "Unknown Author")
    N = get_terminal_size()[0]
    # Output formatting designed nicely for terminal splash screens
    print("\n" + "─" * N)
    print(f'\033[5;96m"{quote_text}"\033[0m')
    print(f"\033[5;94m  — {author_text}\033[0m")
    print("─" * N + "\n")
if __name__ == "__main__":
    display_random_quote()
