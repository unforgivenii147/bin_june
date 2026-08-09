#!/data/data/com.termux/files/home/.local/bin/python
"""
Spell check all text files in current directory recursively using pyspellchecker.
Supports parallel processing and optional auto-fix mode.
"""

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

from spellchecker import SpellChecker

# Common text file extensions to check
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".rst",
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".json",
    ".yaml",
    ".yml",
    ".cfg",
    ".ini",
    ".conf",
    ".log",
    ".csv",
    ".xml",
    ".sh",
    ".bat",
    ".ps1",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".rs",
    ".go",
    ".rb",
    ".php",
    ".sql",
}


def find_text_files(root_dir: Path, extensions: set = None) -> List[Path]:
    """Find all text files recursively in the given directory."""
    if extensions is None:
        extensions = TEXT_EXTENSIONS
    text_files = []
    for path in root_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            text_files.append(path)
    return text_files


def extract_words(text: str) -> List[Tuple[str, int, int]]:
    """
    Extract words from text along with their positions.
    Returns list of (word, start_pos, end_pos) tuples.
    """
    import re

    words = []
    for match in re.finditer(r"\b[a-zA-Z]+\b", text):
        words.append((match.group(), match.start(), match.end()))
    return words


def check_file(file_path: Path) -> Dict:
    """
    Check a single file for misspelled words.
    Returns a dictionary with file path and misspelled words info.
    """
    try:
        spell = SpellChecker()
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        words = extract_words(content)
        misspellings = []
        for word, start, end in words:
            if len(word) > 1 and word.lower() not in spell:  # Skip single chars
                # Check if it's a known word or misspelling
                if word.lower() != spell.correction(word.lower()):
                    misspellings.append(
                        {
                            "word": word,
                            "position": (start, end),
                            "correction": spell.correction(word.lower()),
                            "candidates": list(spell.candidates(word.lower()))[:5],
                        }
                    )
        return {"file": str(file_path), "misspellings": misspellings, "content": content}
    except Exception as e:
        return {"file": str(file_path), "error": str(e), "misspellings": [], "content": None}


def fix_file(file_path: Path, corrections: Dict[str, str]) -> bool:
    """
    Apply corrections to a file in-place.
    Returns True if successful, False otherwise.
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        words = extract_words(content)
        # Apply corrections from end to start to preserve positions
        corrections_to_apply = []
        for word, start, end in words:
            if word.lower() in corrections:
                corrections_to_apply.append((start, end, corrections[word.lower()]))
        # Sort by position in reverse to apply changes from end to start
        corrections_to_apply.sort(key=lambda x: x[0], reverse=True)
        # Apply corrections
        for start, end, correction in corrections_to_apply:
            content = content[:start] + correction + content[end:]
        file_path.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Error fixing {file_path}: {e}", file=sys.stderr)
        return False


def process_files_parallel(files: List[Path], max_workers: int = None) -> Dict:
    """
    Process multiple files in parallel using ProcessPoolExecutor.
    Returns combined results.
    """
    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all files for processing
        future_to_file = {executor.submit(check_file, file_path): file_path for file_path in files}
        # Process completed tasks
        for i, future in enumerate(as_completed(future_to_file), 1):
            file_path = future_to_file[future]
            try:
                result = future.result()
                results[str(file_path)] = result
                if i % 10 == 0 or i == len(files):
                    print(f"\rProcessed {i}/{len(files)} files...", end="", flush=True)
            except Exception as e:
                print(f"\nError processing {file_path}: {e}", file=sys.stderr)
                results[str(file_path)] = {"file": str(file_path), "error": str(e), "misspellings": [], "content": None}
    print()  # New line after progress
    return results


def display_results(results: Dict, show_candidates: bool = False):
    """Display spell checking results in a readable format."""
    total_misspellings = 0
    files_with_errors = 0
    for file_path, result in sorted(results.items()):
        if result.get("error"):
            print(f"\n❌ Error in {file_path}: {result['error']}")
            continue
        misspellings = result["misspellings"]
        if not misspellings:
            continue
        files_with_errors += 1
        total_misspellings += len(misspellings)
        rel_path = Path(file_path).relative_to(Path.cwd())
        print(f"\n📄 {rel_path} ({len(misspellings)} misspellings)")
        print("-" * 42)
        for ms in misspellings[:10]:  # Show first 10 per file
            context = get_context(result["content"], ms["position"])
            print(f"  • Line {context['line']}: '{ms['word']}' → '{ms['correction']}'")
            if show_candidates and ms["candidates"]:
                print(f"    Candidates: {', '.join(ms['candidates'])}")
            if context["text"]:
                print(f"    Context: {context['text']}")
        if len(misspellings) > 10:
            print(f"  ... and {len(misspellings) - 10} more")
    print("\n" + "=" * 42)
    print(f"📊 Summary: {files_with_errors} files with {total_misspellings} total misspellings")
    print("=" * 42)


def get_context(content: str, position: Tuple[int, int], window: int = 40) -> Dict:
    """Get the line number and surrounding context for a word position."""
    if not content:
        return {"line": 0, "text": ""}
    start, end = position
    before_start = max(0, start - window)
    after_end = min(len(content), end + window)
    # Count lines up to the word
    line_num = content[:start].count("\n") + 1
    # Get surrounding text
    before = content[before_start:start].strip()
    after = content[end:after_end].strip()
    if before:
        before = "..." + before if before_start > 0 else before
    if after:
        after = after + "..." if after_end < len(content) else after
    return {"line": line_num, "text": f"{before} [{content[start:end]}] {after}".strip()}


def confirm_action(prompt: str) -> bool:
    """Ask user for confirmation."""
    while True:
        response = input(f"{prompt} (y/n): ").lower().strip()
        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False
        print("Please answer 'y' or 'n'")


def main():
    parser = argparse.ArgumentParser(
        description="Find and optionally fix misspelled words in text files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Check current directory recursively
  %(prog)s -a                 # Auto-fix all found misspellings
  %(prog)s -a --interactive   # Confirm each correction
  %(prog)s -w 8               # Use 8 worker processes
  %(prog)s -e .txt .md        # Only check .txt and .md files
        """,
    )
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("-a", "--autofix", action="store_true", help="Automatically fix misspelled words in-place")
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Ask for confirmation before each fix (only with -a)"
    )
    parser.add_argument(
        "-w", "--workers", type=int, default=None, help="Number of parallel workers (default: CPU count)"
    )
    parser.add_argument("-e", "--extensions", nargs="+", help="File extensions to check (default: common text files)")
    parser.add_argument("-c", "--candidates", action="store_true", help="Show candidate corrections")
    parser.add_argument("--min-length", type=int, default=2, help="Minimum word length to check (default: 2)")
    args = parser.parse_args()
    # Set up extensions
    if args.extensions:
        extensions = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions}
    else:
        extensions = TEXT_EXTENSIONS
    # Find files
    root_dir = Path(args.directory).resolve()
    if not root_dir.exists():
        print(f"Error: Directory '{root_dir}' does not exist", file=sys.stderr)
        sys.exit(1)
    print(f"🔍 Scanning {root_dir} for text files...")
    files = find_text_files(root_dir, extensions)
    if not files:
        print("No text files found.")
        return
    print(f"📁 Found {len(files)} text files to check")
    print(f"⚡ Using {args.workers or 'default'} worker processes")
    # Process files
    print("\n🔄 Checking spelling...")
    results = process_files_parallel(files, args.workers)
    # Display results
    display_results(results, args.candidates)
    # Auto-fix if requested
    if args.autofix:
        total_misspellings = sum(len(r["misspellings"]) for r in results.values() if not r.get("error"))
        if total_misspellings == 0:
            print("✅ No misspellings to fix!")
            return
        if args.interactive:
            proceed = confirm_action(f"\n🔧 Found {total_misspellings} misspellings. Apply fixes?")
        else:
            print(f"\n🔧 Auto-fixing {total_misspellings} misspellings...")
            proceed = True
        if proceed:
            fixed_count = 0
            for file_path, result in sorted(results.items()):
                if result.get("error") or not result["misspellings"]:
                    continue
                # Build correction mapping
                corrections = {}
                for ms in result["misspellings"]:
                    if args.interactive:
                        print(f"\nFile: {file_path}")
                        print(f"  Word: '{ms['word']}'")
                        print(f"  Suggested: '{ms['correction']}'")
                        if ms["candidates"]:
                            print(f"  Candidates: {', '.join(ms['candidates'])}")
                        action = input("  Apply this fix? (y/n/s[kip all]/q[uit]): ").lower().strip()
                        if action in ["q", "quit"]:
                            print("Quitting...")
                            return
                        elif action in ["s", "skip"]:
                            continue
                        elif action not in ["y", "yes"]:
                            continue
                    corrections[ms["word"].lower()] = ms["correction"]
                if corrections:
                    if fix_file(Path(file_path), corrections):
                        fixed_count += len(corrections)
                        print(f"✅ Fixed {file_path}")
            print(f"\n✅ Fixed {fixed_count} misspellings across multiple files")
        else:
            print("❌ Fix cancelled")


if __name__ == "__main__":
    main()
