#!/data/data/com.termux/files/usr/bin/python
"""
Translate non-English comments, docstrings, and print() strings
in Python files recursively from the current directory.
"""

import ast
import io
import multiprocessing
import re
import time
import tokenize
from pathlib import Path

from deep_translator import GoogleTranslator
from dh import DOC_TH1, DOC_TH2
from langdetect import DetectorFactory, detect

DetectorFactory.seed = 0  # Make results deterministic


# ── config ────────────────────────────────────────────────────────────────────
TARGET_LANG = "en"
DELAY_SECONDS = 0.5  # pause between translator calls (per worker)
MAX_WORKERS = 4  # parallel file workers
# ─────────────────────────────────────────────────────────────────────────────

SHEBANG_PREFIX = "#!/"
KNOWN_ENGLISH_TOKENS = {
    "TODO",
    "FIXME",
    "HACK",
    "XXX",
    "NOTE",
    "BUG",
    "pylint",
    "noqa",
    "type: ignore",
    "pragma",
    "coding:",
    "encoding:",
    "charset:",
    "DRYRUN",
    "DRY-RUN",
    "RESCURSIVE MODE ENABLED",
    ".gitignore",
}

# Unicode ranges for non-Latin scripts (scripts that don't use Latin alphabet)
NON_LATIN_UNICODE_RANGES = [
    # Arabic & Persian (Arabic script) - NO Latin characters
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
    (0x1EE00, 0x1EEFF),  # Arabic Mathematical Alphabetic Symbols
    # Russian, Ukrainian, etc. (Cyrillic) - NO Latin characters
    (0x0400, 0x04FF),  # Cyrillic
    (0x0500, 0x052F),  # Cyrillic Supplement
    # Japanese (Hiragana, Katakana, Kanji) - NO Latin characters
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
    (0x31F0, 0x31FF),  # Katakana Phonetic Extensions
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
    (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
    # Chinese (Hanzi) - NO Latin characters
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
    (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
    # Korean (Hangul) - NO Latin characters
    (0xAC00, 0xD7AF),  # Hangul Syllables
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0xA960, 0xA97F),  # Hangul Jamo Extended-A
    (0xD7B0, 0xD7FF),  # Hangul Jamo Extended-B
    # Hebrew - NO Latin characters
    (0x0590, 0x05FF),  # Hebrew
    # Greek - NO Latin characters (though Greek uses a different alphabet)
    (0x0370, 0x03FF),  # Greek and Coptic
    # Thai - NO Latin characters
    (0x0E00, 0x0E7F),  # Thai
    # Devanagari (Hindi, Sanskrit, etc.) - NO Latin characters
    (0x0900, 0x097F),  # Devanagari
    # Other South Asian scripts (no Latin)
    (0x0980, 0x09FF),  # Bengali
    (0x0A00, 0x0A7F),  # Gurmukhi
    (0x0A80, 0x0AFF),  # Gujarati
    (0x0B00, 0x0B7F),  # Oriya
    (0x0B80, 0x0BFF),  # Tamil
    (0x0C00, 0x0C7F),  # Telugu
    (0x0C80, 0x0CFF),  # Kannada
    (0x0D00, 0x0D7F),  # Malayalam
    (0x0D80, 0x0DFF),  # Sinhala
    (0x0E80, 0x0EFF),  # Lao
    # Georgian
    (0x10A0, 0x10FF),  # Georgian
    # Armenian
    (0x0530, 0x058F),  # Armenian
    # Ethiopic
    (0x1200, 0x137F),  # Ethiopic
    # Cherokee
    (0x13A0, 0x13FF),  # Cherokee
    # Canadian Aboriginal Syllabics
    (0x1400, 0x167F),  # Canadian Aboriginal Syllabics
    # Mongolian
    (0x1800, 0x18AF),  # Mongolian
    # Tifinagh (Berber)
    (0x2D30, 0x2D7F),  # Tifinagh
    # Myanmar (Burmese)
    (0x1000, 0x109F),  # Myanmar
    # Khmer (Cambodian)
    (0x1780, 0x17FF),  # Khmer
    # Other scripts without Latin
    (0x10300, 0x1032F),  # Old Italic
    (0x10330, 0x1034F),  # Gothic
    (0x10400, 0x1044F),  # Deseret
    (0x10800, 0x1083F),  # Cypriot Syllabary
    (0x10900, 0x1091F),  # Phoenician
    (0x10A00, 0x10A5F),  # Kharoshthi
    (0x10C00, 0x10C4F),  # Old Turkic
]

# Unicode range for Latin script (to explicitly exclude)
LATIN_RANGES = [
    (0x0000, 0x007F),  # Basic Latin
    (0x0080, 0x00FF),  # Latin-1 Supplement
    (0x0100, 0x017F),  # Latin Extended-A
    (0x0180, 0x024F),  # Latin Extended-B
    (0x1E00, 0x1EFF),  # Latin Extended Additional
    (0x2C60, 0x2C7F),  # Latin Extended-C
    (0xA720, 0xA7FF),  # Latin Extended-D
    (0xAB30, 0xAB6F),  # Latin Extended-E
]

# Vietnamese uses Latin script with diacritics - we should NOT translate it
# as it uses the Latin alphabet


def is_english_alphabet(text: str) -> bool:
    """Check if text contains only Latin/English alphabet characters."""
    for char in text:
        # If it has a Unicode character that's definitely not Latin
        code_point = ord(char)

        # Check if it's in Latin ranges
        is_latin = False
        for start, end in LATIN_RANGES:
            if start <= code_point <= end:
                is_latin = True
                break

        # If it's not in Latin ranges and it's an alphabetic character, it's non-English
        if not is_latin and char.isalpha():
            return False

        # If it's a digit or punctuation, it's fine
        if not char.isalpha() and not char.isspace():
            continue

    return True


def has_non_latin_alphabet(text: str) -> bool:
    """
    Check if text contains alphabetic characters from non-Latin scripts.
    Returns True if there's at least one non-Latin alphabetic character.
    """
    for char in text:
        if char.isalpha() and not is_english_alphabet(char):
            return True
    return False


def should_skip(text: str) -> bool:
    """Return True if text should NOT be checked for translation."""
    clean = text.strip()

    # Skip shebangs
    if clean.startswith(SHEBANG_PREFIX):
        return True

    # Skip if it contains only English/Latin characters (this is the key change)
    if is_english_alphabet(clean):
        # If it's all English alphabet, it's English text
        return True

    # Skip known tokens (even if they have mixed scripts)
    if any(word in clean.upper() for word in KNOWN_ENGLISH_TOKENS):
        return True

    # Skip if it's just punctuation/symbols with no alphabetic characters
    if not any(c.isalpha() for c in clean):
        return True

    return False


def is_non_english(text: str) -> bool:
    """
    Strict check for non-English text - only translates if there are
    non-Latin alphabetic characters present.
    """
    clean = text.strip()

    # Quick rejections
    if not clean or len(clean) < 2:
        return False

    # Check if it has non-Latin alphabet characters
    if not has_non_latin_alphabet(clean):
        return False  # No non-Latin characters, so it's English/Latin

    # Check skip conditions
    if should_skip(clean):
        return False

    # Double-check with langdetect to confirm
    try:
        detected_lang = detect(clean)
        # Only return True if langdetect confirms it's not English
        # and it has non-Latin characters
        if detected_lang != "en":
            # But also verify it actually has non-Latin characters
            if has_non_latin_alphabet(clean):
                return True
    except Exception:
        # If langdetect fails, but we have non-Latin characters, it's likely non-English
        return has_non_latin_alphabet(clean)

    return False


def translate_text(text: str) -> str:
    """Translate *text* to English; return original on failure."""
    try:
        result = GoogleTranslator(source="auto", target=TARGET_LANG).translate(text)
        time.sleep(DELAY_SECONDS)
        return result if result else text
    except Exception as exc:
        print(f"  [warn] translation failed: {exc}")
        return text


# ── token-level extraction & replacement ─────────────────────────────────────


def find_print_string_tokens(source: str):
    """
    Yield (start_byte_offset, end_byte_offset, string_value) for every
    string literal that is a direct argument of a print() call.
    Works at the AST level so we get exact locations.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return

    lines = source.splitlines(keepends=True)
    # build cumulative byte-offset table  (line numbers are 1-based in ast)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode()))

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                yield arg.value  # just the string content


def process_file(path: Path) -> bool:
    """
    Translate all non-English tokens in *path*.
    Returns True if the file was modified.
    """
    source = path.read_text(encoding="utf-8")
    tokens = []

    try:
        token_gen = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in token_gen:
            tokens.append(tok)
    except tokenize.TokenError as exc:
        print(f"[skip] {path}: tokenize error – {exc}")
        return False

    # We'll rebuild the source via a list of (start, end, new_text) replacements.
    # Offsets are character positions in the original source.
    lines = source.splitlines(keepends=True)

    def line_col_to_offset(lineno, col):
        """Convert 1-based (line, col) to a character offset in *source*."""
        return sum(len(lines[i]) for i in range(lineno - 1)) + col

    replacements = []  # list of (char_start, char_end, new_source_fragment)

    # ── pass 1: comments ─────────────────────────────────────────────────────
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        raw = tok.string  # e.g.  "#Persian text"
        inner = raw.lstrip("#").strip()
        if not is_non_english(inner):
            continue

        translated = translate_text(inner)
        print(f"  [comment]\n    orig : {inner}\n    trans: {translated}")

        new_comment = "# " + translated
        start = line_col_to_offset(tok.start[0], tok.start[1])
        end = line_col_to_offset(tok.end[0], tok.end[1])
        replacements.append((start, end, new_comment))

    # ── pass 2: string tokens (docstrings + print args) ──────────────────────
    # We need to know which STRING tokens are inside print() calls.
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        print(f"[skip] {path}: ast.parse failed – {exc}")
        return False

    # Collect (line, col) of print-arg string constants
    print_arg_positions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    print_arg_positions.add((arg.col_offset, arg.lineno))

    # Collect docstring node positions
    docstring_positions = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                ds = node.body[0].value
                docstring_positions.add((ds.col_offset, ds.lineno))

    for tok in tokens:
        if tok.type != tokenize.STRING:
            continue

        tok_col_offset = tok.start[1]
        tok_lineno = tok.start[0]

        is_print_arg = (tok_col_offset, tok_lineno) in print_arg_positions
        is_docstring = (tok_col_offset, tok_lineno) in docstring_positions

        if not (is_print_arg or is_docstring):
            continue

        raw = tok.string

        # detect quote style
        if raw.startswith(DOC_TH1) or raw.startswith(DOC_TH2):
            quote = raw[:3]
        elif raw.startswith('"'):
            quote = '"'
        else:
            quote = "'"

        inner = ast.literal_eval(raw)  # actual string value
        if not isinstance(inner, str) or not is_non_english(inner):
            continue

        translated = translate_text(inner)
        label = "docstring" if is_docstring else "print-str"
        print(f"  [{label}]\n    orig : {inner}\n    trans: {translated}")

        # Escape backslashes and the quote character inside the new value
        escaped = translated.replace("\\", "\\\\").replace(quote, "\\" + quote)
        new_tok = quote + escaped + quote

        start = line_col_to_offset(tok.start[0], tok.start[1])
        end = line_col_to_offset(tok.end[0], tok.end[1])
        replacements.append((start, end, new_tok))

    if not replacements:
        return False

    # ── apply replacements (reverse order so offsets stay valid) ─────────────
    replacements.sort(key=lambda r: r[0], reverse=True)
    src_chars = list(source)
    for char_start, char_end, new_frag in replacements:
        src_chars[char_start:char_end] = list(new_frag)

    new_source = "".join(src_chars)

    # ── validate ──────────────────────────────────────────────────────────────
    try:
        ast.parse(new_source)
    except SyntaxError as exc:
        print(f"[error] {path}: result is not valid Python – {exc}. Skipping write.")
        return False

    path.write_text(new_source, encoding="utf-8")
    return True


def process_file_wrapper(path_str: str):
    path = Path(path_str)
    try:
        changed = process_file(path)
        status = "updated" if changed else "no changes"
    except Exception as exc:
        print(f"  [error] {path}: {exc}")


def main():
    py_files = [str(p) for p in Path(".").rglob("*.py") if ".git" not in p.parts]

    if not py_files:
        print("No Python files found.")
        return

    print(f"Found {len(py_files)} Python file(s). Starting with {MAX_WORKERS} workers…\n")

    with multiprocessing.Pool(processes=MAX_WORKERS) as pool:
        pool.map(process_file_wrapper, py_files)


if __name__ == "__main__":
    main()
