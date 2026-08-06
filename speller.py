#!/data/data/com.termux/files/home/.local/bin/python
import argparse
import re
from spellchecker import SpellChecker
def process_file(filepath, autofix=False):
    spell = SpellChecker()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found.")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    misspelled_count = 0
    # Function to process each word found by the regex
    def check_and_replace(match):
        nonlocal misspelled_count
        word = match.group(0)
        # Skip acronyms or words without letters (e.g., numbers, punctuation-only)
        if not word.isalpha():
            return word
        # Check if the lowercase version of the word is misspelled
        if word.lower() not in spell:
            misspelled_count += 1
            if autofix:
                # Get the one most likely correction
                correction = spell.correction(word.lower())
                # If no correction is found, keep the original word
                if not correction:
                    return word
                # Preserve original capitalization
                if word.istitle():
                    return correction.capitalize()
                elif word.isupper():
                    return correction.upper()
                else:
                    return correction
            else:
                # If not autofixing, just print the misspelled word and suggestions
                candidates = spell.candidates(word.lower())
                suggestions = ", ".join(candidates) if candidates else "No suggestions"
                print(f"Misspelled: '{word}' | Suggestions: {suggestions}")
                return word
        return word
    # Regex to find words (including those with apostrophes like "don't")
    # \b matches word boundaries, [\w']+ matches word characters and apostrophes
    updated_text = re.sub(r"[\w']+", check_and_replace, text)
    if autofix and misspelled_count > 0:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(updated_text)
            print(f"\nAutofixed {misspelled_count} misspelled word(s) in '{filepath}'.")
        except Exception as e:
            print(f"Error writing to file: {e}")
    elif autofix and misspelled_count == 0:
        print("No misspelled words found to autofix.")
    else:
        if misspelled_count == 0:
            print("No misspelled words found.")
        else:
            print(f"\nFound {misspelled_count} misspelled word(s). Run with -a to autofix.")
if __name__ == "__main__":
    # Set up the command line argument parser
    parser = argparse.ArgumentParser(description="Detect and optionally autofix misspelled words in a file.")
    parser.add_argument("file", help="Path to the text file to check")
    parser.add_argument(
        "-a", "--autofix", action="store_true", help="Automatically correct misspelled words in the file"
    )
    args = parser.parse_args()
    process_file(args.file, args.autofix)
