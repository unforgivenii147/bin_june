#!/data/data/com.termux/files/usr/bin/python
"""
Auto typo fixer with pattern learning.
Learns from common substitution errors (b→n, 8→i, etc.) and user corrections.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Common substitution errors (your examples)
COMMON_SUBSTITUTIONS = {
    # Your specific patterns
    "b": "n",
    "n": "b",  # b↔n (pribt→print)
    "8": "i",  # 8→i
    "9": "o",  # 9→o
    "0": "p",  # 0→p
    "s": "a",  # s→a
    "y": "t",
    "t": "y",  # y↔t
    # Additional common patterns
    "5": "s",
    "s": "5",
    "1": "l",
    "l": "1",
    "2": "z",
    "z": "2",
    "3": "e",
    "e": "3",
    "4": "a",
    "a": "4",
    "6": "g",
    "g": "6",
    "7": "t",
    "t": "7",
    "@": "a",
    "a": "@",
    "!": "i",
    "i": "!",
}

# Common adjacent key typos (QWERTY layout)
QWERTY_ADJACENT = {
    "q": "w",
    "w": "qe",
    "e": "wr",
    "r": "et",
    "t": "ry",
    "y": "tu",
    "u": "yi",
    "i": "uo",
    "o": "ip",
    "p": "o",
    "a": "sw",
    "s": "ad",
    "d": "sf",
    "f": "dg",
    "g": "fh",
    "h": "gj",
    "j": "hk",
    "k": "jl",
    "l": "k",
    "z": "xa",
    "x": "zc",
    "c": "xv",
    "v": "cb",
    "b": "vn",
    "n": "bm",
    "m": "n",
}


class PatternLearner:
    """Learns from typos and user corrections"""

    def __init__(self, learning_db_path: str = "typo_patterns.json") -> None:
        self.learning_db_path = learning_db_path
        self.substitution_patterns = dict(COMMON_SUBSTITUTIONS)
        self.learned_corrections = {}  # wrong_word -> correct_word
        self.error_frequency = defaultdict(int)  # pattern -> count
        self.context_rules = []  # learned context-based rules

        self._load_learning_db()

    def _load_learning_db(self) -> None:
        """Load previously learned patterns"""
        if Path(self.learning_db_path).exists():
            try:
                with open(self.learning_db_path, "r") as f:
                    data = json.load(f)
                    self.learned_corrections = data.get("corrections", {})
                    self.error_frequency.update(data.get("frequencies", {}))
                    self.context_rules = data.get("context_rules", [])
                print(f"Loaded {len(self.learned_corrections)} learned corrections", file=sys.stderr)
            except Exception as e:
                print(f"Error loading learning DB: {e}", file=sys.stderr)

    def save(self) -> None:
        """Save learned patterns"""
        data = {
            "corrections": self.learned_corrections,
            "frequencies": dict(self.error_frequency),
            "context_rules": self.context_rules,
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.learning_db_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved learning patterns to {self.learning_db_path}", file=sys.stderr)

    def apply_substitutions(self, word: str) -> str:
        """Apply common substitution patterns to guess intended word"""
        # Try single character substitutions first
        candidates = []

        # 1. Apply learned exact corrections
        if word in self.learned_corrections:
            candidates.append((self.learned_corrections[word], 1.0))

        # 2. Try character substitution patterns
        for i, char in enumerate(word):
            if char in self.substitution_patterns:
                corrected = word[:i] + self.substitution_patterns[char] + word[i + 1 :]
                candidates.append((corrected, 0.9))

        # 3. Try multiple substitutions (for 2+ character errors)
        multi_corrected = word
        multi_changes = 0
        for i, char in enumerate(word):
            if char in self.substitution_patterns:
                multi_corrected = multi_corrected[:i] + self.substitution_patterns[char] + multi_corrected[i + 1 :]
                multi_changes += 1
        if multi_changes > 0 and multi_corrected != word:
            candidates.append((multi_corrected, 0.8 - (multi_changes * 0.1)))

        # Return best candidate (highest confidence)
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        return word

    def learn_from_correction(self, wrong: str, correct: str, context: str = "") -> None:
        """Learn from a user correction"""
        if wrong == correct:
            return

        # Store exact correction
        self.learned_corrections[wrong] = correct
        self.error_frequency[wrong] += 1

        # Learn character substitution patterns
        if len(wrong) == len(correct):
            for w_char, c_char in zip(wrong, correct):
                if w_char != c_char:
                    pattern = f"{w_char}→{c_char}"
                    self.error_frequency[pattern] += 1

                    # If pattern appears frequently, add to substitution patterns
                    if self.error_frequency[pattern] > 2:
                        self.substitution_patterns[w_char] = c_char
                        print(f"  Learned pattern: '{w_char}' → '{c_char}'", file=sys.stderr)

        # Learn length-based corrections (missing/extra letters)
        elif len(wrong) == len(correct) + 1:  # extra letter
            for i in range(len(wrong)):
                if wrong[:i] + wrong[i + 1 :] == correct:
                    pattern = f"delete '{wrong[i]}'"
                    self.error_frequency[pattern] += 1

        elif len(wrong) == len(correct) - 1:  # missing letter
            for i in range(len(correct)):
                if correct[:i] + correct[i + 1 :] == wrong:
                    pattern = f"insert '{correct[i]}'"
                    self.error_frequency[pattern] += 1

        # Save after learning
        self.save()


class TypoFixerWithLearning:
    def __init__(self, preview: bool = True, learning_db: str = "typo_patterns.json") -> None:
        self.preview = preview
        self.learner = PatternLearner(learning_db)
        self.changes_made = 0
        self.files_processed = 0
        self.interactive_mode = False

        # Load valid words from NLTK
        self.valid_words = set()
        self._load_word_list()

        # Add common programming terms
        self.valid_words.update({
            "print",
            "function",
            "class",
            "def",
            "return",
            "import",
            "from",
            "true",
            "false",
            "null",
            "undefined",
            "const",
            "let",
            "var",
            "async",
            "await",
            "promise",
            "callback",
            "component",
            "react",
        })

    def _load_word_list(self) -> None:
        """Load dictionary words"""
        try:
            import nltk
            from nltk.corpus import words

            try:
                nltk.data.find("corpora/words.zip")
            except LookupError:
                nltk.download("words", quiet=True)
            self.valid_words.update(w.lower() for w in words.words())
            print(f"Loaded {len(self.valid_words)} dictionary words", file=sys.stderr)
        except:
            print("Warning: Could not load NLTK words", file=sys.stderr)
            # Fallback common words
            common = {
                "the",
                "be",
                "to",
                "of",
                "and",
                "a",
                "in",
                "that",
                "have",
                "i",
                "it",
                "for",
                "not",
                "on",
                "with",
                "he",
                "as",
                "you",
                "do",
                "at",
            }
            self.valid_words.update(common)

    def is_valid_word(self, word: str) -> bool:
        """Check if word appears valid"""
        if len(word) < 3:
            return True
        # All caps acronyms
        if word.isupper() and 2 <= len(word) <= 5:
            return True
        return word.lower() in self.valid_words

    def suggest_correction(self, word: str, context: str = "") -> Optional[str]:
        """Suggest correction using multiple strategies"""
        if self.is_valid_word(word):
            return None

        # Strategy 1: Apply learned patterns
        pattern_corrected = self.learner.apply_substitutions(word)
        if pattern_corrected != word and self.is_valid_word(pattern_corrected):
            return pattern_corrected

        # Strategy 2: Try adjacent key errors
        for i, char in enumerate(word):
            if char in QWERTY_ADJACENT:
                for replacement in QWERTY_ADJACENT[char]:
                    corrected = word[:i] + replacement + word[i + 1 :]
                    if self.is_valid_word(corrected):
                        return corrected

        # Strategy 3: Check if it's a learned correction
        if word in self.learner.learned_corrections:
            return self.learner.learned_corrections[word]

        # Strategy 4: Use difflib as last resort
        try:
            from difflib import get_close_matches

            matches = get_close_matches(word.lower(), self.valid_words, n=1, cutoff=0.75)
            if matches:
                # Preserve case
                if word[0].isupper():
                    return matches[0].capitalize()
                return matches[0]
        except:
            pass

        return None

    def interactive_fix(self, word: str, line: str) -> str:
        """Ask user for correction and learn from it"""
        print(f"\nUnknown word: '{word}'")
        print(f"Context: {line.strip()}")

        # Try to suggest
        suggestion = self.suggest_correction(word)
        if suggestion:
            print(f"Suggested: '{suggestion}'", file=sys.stderr)

        while True:
            choice = input(f"Fix '{word}'? [y(es)/n(o)/e(dit)/l(earn)]: ").lower()
            if choice == "y" and suggestion:
                self.learner.learn_from_correction(word, suggestion, line)
                return suggestion
            elif choice == "y" and not suggestion:
                manual = input("Enter correction: ")
                self.learner.learn_from_correction(word, manual, line)
                return manual
            elif choice == "e":
                manual = input("Enter correction: ")
                self.learner.learn_from_correction(word, manual, line)
                return manual
            elif choice == "l":
                print(f"Learning '{word}' as valid word")
                self.valid_words.add(word.lower())
                self.learner.learned_corrections[word] = word
                return word
            elif choice == "n":
                return word

    def fix_file(self, filepath: Path) -> bool:
        """Process a single file"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"  Error reading {filepath}: {e}", file=sys.stderr)
            return False

        fixed_lines = []
        changes = 0

        word_pattern = re.compile(r"\b([a-zA-Z]+(?:[-\'][a-zA-Z]+)*)\b")

        for line_num, line in enumerate(lines, 1):
            fixed_line = line

            def replace_word(match):
                nonlocal changes
                word = match.group(1)

                # Skip short words and code-looking words
                if len(word) <= 2 or word.isupper():
                    return word

                # Check for correction
                if not self.is_valid_word(word):
                    correction = self.suggest_correction(word, line)

                    if correction:
                        changes += 1
                        if self.preview:
                            print(f"  Line {line_num}: '{word}' → '{correction}'", file=sys.stderr)
                        return correction
                    elif self.interactive_mode:
                        correction = self.interactive_fix(word, line)
                        if correction != word:
                            changes += 1
                        return correction

                return word

            fixed_line = word_pattern.sub(replace_word, line)
            fixed_lines.append(fixed_line)

        if changes > 0 and not self.preview:
            backup = filepath.with_suffix(filepath.suffix + ".bak")
            shutil.copy2(filepath, backup)

            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(fixed_lines)
            print(f"  Fixed {changes} typo(s) in {filepath}", file=sys.stderr)
        elif changes > 0 and self.preview:
            print(f"  Would fix {changes} typo(s) in {filepath}", file=sys.stderr)

        self.changes_made += changes
        return changes > 0

    def process_directory(self, cwd: str) -> None:
        """Process all files recursively"""
        root_path = Path(cwd)
        extensions = {".md", ".py", ".toml", ".json", ".html", ".css", ".js", ".txt"}

        for ext in extensions:
            for filepath in root_path.rglob(f"*{ext}"):
                if filepath.is_file():
                    self.files_processed += 1
                    print(f"\nProcessing: {filepath}", file=sys.stderr)
                    self.fix_file(filepath)

        print(f"\nSummary: Processed {self.files_processed} files", file=sys.stderr)
        print(f"Active patterns: {len(self.learner.substitution_patterns)}", file=sys.stderr)
        print(f"Learned corrections: {len(self.learner.learned_corrections)}", file=sys.stderr)

        if self.changes_made > 0:
            self.learner.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-fix typos with pattern learning")
    parser.add_argument("--apply", action="store_true", help="Actually apply fixes")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode (learn from each fix)")
    parser.add_argument("--dir", type=str, default=".", help="Directory to process")
    parser.add_argument("--db", type=str, default="typo_patterns.json", help="Learning database file")
    parser.add_argument("--show-patterns", action="store_true", help="Show learned patterns and exit")

    args = parser.parse_args()

    if args.show_patterns:
        learner = PatternLearner(args.db)
        print(f"\nLearned Corrections ({len(learner.learned_corrections)}):")
        for wrong, correct in sorted(learner.learned_corrections.items()):
            print(f"  {wrong} → {correct} (seen {learner.error_frequency[wrong]} times)")
        print(f"\nActive Substitution Patterns ({len(learner.substitution_patterns)}):")
        for wrong, correct in sorted(learner.substitution_patterns.items()):
            if wrong in COMMON_SUBSTITUTIONS:
                print(f"  {wrong} → {correct} (default)")
            else:
                print(f"  {wrong} → {correct} (learned)")
        return

    fixer = TypoFixerWithLearning(preview=not args.apply, learning_db=args.db)
    fixer.interactive_mode = args.interactive
    fixer.process_directory(args.dir)


if __name__ == "__main__":
    main()
