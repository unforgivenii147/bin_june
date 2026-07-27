#!/data/data/com.termux/files/home/.local/bin/python
import json
import os

FILE_NAME = "/sdcard/data/quotes/quotes.json"


def sort_quotes_by_author():
    # 1. Check if the file exists before reading
    if not os.path.exists(FILE_NAME):
        print(f"Error: '{FILE_NAME}' could not be found.")
        return

    # 2. Read the raw data from the file
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        try:
            quotes = json.load(f)
        except json.JSONDecodeError:
            print("Error: 'quotes.json' is empty or contains invalid formatting.")
            return

    # 3. Sort the data list in place by the 'author' key
    # .get() handles any entries missing an author key gracefully by defaulting to an empty string
    quotes.sort(key=lambda item: item.get("author", "").lower())

    # 4. Save the freshly sorted array back to disk with nice indentation
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(quotes, f, indent=2, ensure_ascii=False)

    print(f"Success: Sorted all quotes alphabetically by author in '{FILE_NAME}'.")


if __name__ == "__main__":
    sort_quotes_by_author()
