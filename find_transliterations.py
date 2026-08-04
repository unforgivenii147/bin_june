#!/data/data/com.termux/files/home/.local/bin/python
"""
Find transliterated Persian words in a dictionary JSON file.
Detects entries where the "translation" is just the English phonetic spelling
of the Persian word rather than an actual translation.
"""

import argparse
import json
import re
import sys

from rapidfuzz import fuzz


def is_finglish(text: str, finglish: str) -> int:
    persian_map = {
        "ا": "a",
        "آ": "a",
        "ب": "b",
        "پ": "p",
        "ت": "t",
        "ث": "s",
        "ج": "j",
        "چ": "ch",
        "ح": "h",
        "خ": "kh",
        "د": "d",
        "ذ": "z",
        "ر": "r",
        "ز": "z",
        "ژ": "zh",
        "س": "s",
        "ش": "sh",
        "ص": "s",
        "ض": "z",
        "ط": "t",
        "ظ": "z",
        "ع": "a",
        "غ": "gh",
        "ف": "f",
        "ق": "gh",
        "ک": "k",
        "گ": "g",
        "ل": "l",
        "م": "m",
        "ن": "n",
        "ه": "h",
    }
    words = text.split(" ")
    processed_words = []
    for word in words:
        if not word:
            processed_words.append("")
            continue
        processed_word = ""
        chars = list(word)
        for i, char in enumerate(chars):
            if char == "و":
                if i == 0:
                    processed_word += "v"
                else:
                    processed_word += "o"
            elif char == "ی":
                if i == 0 or i == len(chars) - 1:
                    processed_word += "y"
                else:
                    processed_word += "i"
            else:
                processed_word += persian_map.get(char, char)
        processed_words.append(processed_word)
    result = "".join(processed_words)
    ratio = fuzz.partial_ratio(result, finglish)
    print(f"partial_ratio({result}, {finglish} = {ratio}")
    if ratio >= 60:
        return True
    return False


def is_transliteration(persian_word, english_word):
    if not english_word or not persian_word:
        return False
    if is_finglish(persian_word, english_word):
        return True
    return False

    """
    if not re.match(r"^[A-Za-z\-\']+$", english_word):
        return False

    if not english_word[0].isupper():
        return False

    # fmt: off
    common_english_words = {"pump", "enough", "window", "line", "scissors", "science", "stomach", "disgust", "country", "burn", "journey", "note", "attempt", "before", "second", "bit", "make", "land", "door", "foolish", "bitter", "basket", "milk", "big", "tomorrow", "knee", "hollow", "root", "bird", "room", "possible", "the", "male", "office", "tree", "roof", "hard", "just", "wet", "most", "light", "limit", "across", "scale", "will", "laugh", "skirt", "doubt", "he", "screw", "linen", "day", "one", "clear", "ear", "bone", "meat", "cloth", "different", "branch", "clock", "meal", "clean", "argument", "simple", "education", "cloud", "moon", "she", "act", "oil", "ready", "destruction", "good", "law", "map", "hair", "pot", "test", "may", "two", "structure", "basin", "birth", "government", "man", "cold", "idea", "cake", "band", "up", "us", "punishment", "colour", "slip", "canvas", "after", "growth", "move", "business", "angry", "angle", "direction", "feather", "answer", "peace", "receipt", "bed", "agreement", "bee", "strong", "it", "measure", "mixed", "in", "match", "ice", "if", "have", "sudden", "bent", "square", "complex", "lock", "full", "nation", "home", "narrow", "red", "secret", "political", "brother", "summer", "almost", "so", "drink", "shock", "sort", "wax", "spoon", "drain", "way", "war", "shade", "shake", "shame", "chin", "shelf", "space", "spade", "elastic", "regular", "horse", "house", "dress", "sharp", "sheep", "shirt", "short", "stocking", "theory", "sign", "between", "take", "cook", "cause", "religion", "very", "go", "order", "value", "sand", "back", "breath", "with", "out", "gun", "our", "list", "leg", "transport", "sponge", "respect", "brass", "send", "brain", "brown", "let", "brick", "brush", "brake", "bread", "pain", "waiting", "coat", "chemical", "coal", "fall", "from", "damage", "air", "harmony", "separate", "present", "egg", "come", "among", "comfort", "library", "polish", "comb", "left", "distribution", "shoe", "fat", "place", "plane", "plate", "parallel", "far", "credit", "organization", "my", "father", "finger", "plant", "me", "error", "when", "discovery", "down", "snow", "mist", "pin", "insurance", "warm", "sea", "complete", "pig", "bath", "see", "stop", "near", "edge", "sex", "week", "arch", "friend", "discussion", "harbour", "year", "pull", "against", "division", "circle", "kiss", "fowl", "open", "property", "dirty", "language", "society", "base", "pocket", "poor", "porter", "powder", "wheel", "where", "while", "which", "white", "we", "late", "company", "frequent", "push", "put", "want", "degree", "crush", "hole", "off", "island", "change", "crack", "cruel", "expert", "crime", "reading", "than", "fear", "rough", "hospital", "round", "debt", "know", "knot", "camera", "button", "that", "machine", "rule", "nail", "tendency", "kettle", "letter", "boat", "feeble", "female", "i", "prison", "comparison", "bulb", "judge", "hanging", "grip", "keep", "under", "reason", "jewel", "mountain", "muscle", "I", "teaching", "dependent", "bottle", "opposite", "tail", "flight", "deep", "jelly", "sky", "as", "at", "gold", "payment", "desire", "seat", "apple", "effect", "ill", "please", "soap", "thunder", "history", "an", "earth", "wire", "god", "equal", "low", "insect", "amusement", "weather", "money", "their", "trouble", "to", "thick", "early", "whip", "think", "delicate", "month", "mouth", "there", "thumb", "thing", "these", "example", "into", "expansion", "past", "feeling", "drop", "free", "winter", "farm", "heart", "responsible", "ever", "snake", "town", "even", "tray", "little", "also", "probable", "exchange", "hope", "cover", "long", "thread", "physical", "they", "cough", "boiling", "tax", "help", "instrument", "copy", "then", "them", "throat", "could", "grain", "green", "loud", "cry", "net", "new", "foot", "other", "bridge", "voice", "apparatus", "violent", "safe", "food", "great", "record", "reward", "group", "position", "grass", "side", "normal", "your", "name", "picture", "trousers", "black", "weight", "blade", "blood", "selection", "son", "king", "kind", "and", "attention", "night", "any", "baby", "cup", "cut", "ant", "strange", "people", "horn", "able", "copper", "give", "awake", "special", "again", "price", "prose", "some", "rail", "rain", "true", "twist", "belief", "print", "tooth", "touch", "butter", "bucket", "leaf", "future", "lead", "leather", "important", "much", "regret", "soft", "tongue", "engine", "potato", "driving", "profit", "south", "ball", "military", "parcel", "solid", "sound", "page", "wrong", "sweet", "level", "memory", "run", "authority", "cheap", "chest", "humour", "card", "care", "garden", "rub", "chalk", "chain", "part", "child", "cart", "chief", "blow", "size", "this", "medical", "knife", "flag", "hat", "range", "cow", "current", "dark", "attack", "step", "stem", "flat", "rest", "produce", "right", "river", "thin", "floor", "knowledge", "berry", "monkey", "morning", "who", "burst", "mark", "mother", "shut", "stitch", "flame", "hammer", "why", "interest", "school", "bell", "wing", "wind", "wine", "minute", "bright", "private", "amount", "though", "about", "word", "loss", "necessary", "work", "dust", "worm", "old", "attraction", "distance", "general", "learning", "time", "fiction", "addition", "paste", "automatic", "pipe", "head", "spring", "through", "salt", "music", "committee", "paint", "swim", "trick", "paper", "train", "condition", "fish", "heat", "trade", "metal", "sad", "iron", "acid", "how", "system", "self", "wave", "digestion", "fact", "need", "play", "secretary", "say", "straight", "silver", "face", "sister", "what", "stick", "steel", "steam", "certain", "curtain", "adjustment", "material", "still", "wise", "ornament", "slope", "stage", "stiff", "stone", "store", "story", "whistle", "nose", "seem", "woman", "sleep", "stamp", "wound", "would", "start", "world", "seed", "slow", "wide", "for", "get", "manager", "invention", "you", "tin", "curve", "city", "thought", "church", "ring", "together", "turn", "offer", "army", "verse", "glove", "question", "chance", "common", "cotton", "substance", "west", "request", "unit", "beautiful", "news", "glass", "fight", "first", "control", "hate", "its", "building", "hook", "false", "field", "fixed", "last", "person", "representative", "quality", "development", "oven", "dead", "silk", "but", "dear", "north", "connection", "umbrella", "girl", "reaction", "relation", "noise", "over", "cat", "top", "young", "design", "natural", "mass", "roll", "here", "bad", "dry", "bag", "opinion", "walk", "wall", "toe", "can", "healthy", "rhythm", "purpose", "tight", "animal", "every", "look", "table", "behaviour", "event", "taste", "tired", "soul", "view", "kick", "now", "end", "not", "pleasure", "rat", "sneeze", "wood", "street", "ray", "wool", "soup", "love", "vessel", "death", "disease", "forward", "small", "decision", "fold", "smash", "smell", "song", "support", "sense", "smile", "experience", "smoke", "goat", "ticket", "loose", "sail", "sun", "sugar", "cheese", "fire", "cushion", "impulse", "sock", "danger", "competition", "hand", "needle", "yellow", "art", "observation", "owner", "number", "guide", "fork", "such", "smooth", "form", "rate", "servant", "surprise", "arm", "jump", "operation", "front", "fruit", "meeting", "market", "balance", "him", "increase", "neck", "family", "eye", "his", "frame", "only", "a", "advertisement", "board", "lip", "bite", "hearing", "quite", "writing", "queen", "fertile", "plough", "yesterday", "quick", "lift", "middle", "living", "quiet", "no", "well", "sticky", "life", "existence", "cord", "collar", "suggestion", "grey", "protest", "body", "process", "cork", "skin", "blue", "broken", "dog", "flower", "point", "motion", "power", "book", "stretch", "pencil", "public", "tall", "daughter", "rice", "talk", "orange", "statement", "boot", "serious", "hour", "all", "do", "same", "till", "happy", "carriage", "pen", "married", "water", "watch", "waste", "wash", "key", "nut", "drawer", "ink", "station", "electric", "ship", "star", "or", "join", "box", "boy", "detail", "east", "of", "conscious", "on", "use", "by", "because", "high", "mind", "like", "fly", "liquid", "mine", "road", "force", "poison", "her", "be", "industry", "approval", "rod", "yes", "account", "nerve"}
    # fmt: on
    if english_word.lower() in common_english_words:
        return False
    if " " in english_word:
        return False

    if len(english_word) <= 2:
        return False

    transliteration_patterns = [
        r"[A-Z][a-z]*[aeiou][a-z]*[aeiou][a-z]*$",  # Multiple vowels
        r"^[A-Z][a-z]*kh[a-z]*$",  # 'kh' sound common in Persian
        r"^[A-Z][a-z]*gh[a-z]*$",  # 'gh' sound common in Persian
        r"^[A-Z][a-z]*sh[a-z]*$",  # 'sh' sound
        r"^[A-Z][a-z]*eh[a-z]*$",  # 'eh' ending
        r"^[A-Z][a-z]*an$",  # 'an' ending
        r"^[A-Z][a-z]*ar$",  # 'ar' ending
        r"^[A-Z][a-z]*ad$",  # 'ad' ending
    ]

    pattern_matches = sum(1 for pattern in transliteration_patterns if re.match(pattern, english_word, re.IGNORECASE))

    if pattern_matches >= 1:
        return True

    # Additional heuristic: if the word looks like a proper noun (capitalized)
    # and doesn't appear to be a common English word, it might be transliteration
    if english_word[0].isupper() and english_word[1:].islower():
        potential_translations = {
            "Morning",
            "Evening",
            "Night",
            "Light",
            "Dark",
            "High",
            "Low",
            "Fast",
            "Slow",
            "Big",
            "Small",
            "Old",
            "New",
            "Good",
            "Bad",
            "True",
            "False",
            "Right",
            "Left",
            "North",
            "South",
            "East",
            "West",
        }

        if english_word not in potential_translations:
            return True

    return False

    """


def find_transliterations(words_dict):
    transliterations = {}
    valid_translations = {}

    for persian_word, english_word in words_dict.items():
        if is_transliteration(persian_word, english_word):
            transliterations[persian_word] = english_word
        else:
            valid_translations[persian_word] = english_word

    return transliterations, valid_translations


def load_json_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{filepath}': {e}")
        sys.exit(1)


def save_json_file(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Find transliterated Persian words in dictionary JSON")
    parser.add_argument("input_file", nargs="?", default="words.json", help="Input JSON file (default: words.json)")
    parser.add_argument(
        "-m", "--move", action="store_true", help="Move found transliterations to errors.json and update words.json"
    )
    parser.add_argument(
        "-e", "--errors-file", default="errors.json", help="Output file for transliterations (default: errors.json)"
    )
    parser.add_argument("-o", "--output", help="Output file for cleaned dictionary (default: overwrite input file)")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output for each transliteration found"
    )

    args = parser.parse_args()

    print(f"Loading dictionary from '{args.input_file}'...")
    words_dict = load_json_file(args.input_file)
    print(f"Loaded {len(words_dict)} entries.")

    print("Analyzing entries for transliterations...")
    transliterations, valid_translations = find_transliterations(words_dict)

    print(f"\nFound {len(transliterations)} potential transliterations:")
    if args.verbose:
        for persian, english in transliterations.items():
            print(f"  {persian}: {english}")
    else:
        for i, (persian, english) in enumerate(transliterations.items()):
            if i < 10:
                print(f"  {persian}: {english}")
            else:
                print(f"  ... and {len(transliterations) - 10} more")
                break

    print(f"Remaining valid translations: {len(valid_translations)}")

    if args.move:
        print(f"\nMoving {len(transliterations)} transliterations to '{args.errors_file}'...")
        save_json_file(transliterations, args.errors_file)

        output_file = args.output if args.output else args.input_file
        print(f"Saving {len(valid_translations)} valid translations to '{output_file}'...")
        save_json_file(valid_translations, output_file)

        print("Done!")
    else:
        print("\nUse -m flag to move these entries to errors.json")
        print(f"Example: python {sys.argv[0]} words.json -m")


if __name__ == "__main__":
    main()
