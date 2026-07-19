#!/data/data/com.termux/files/usr/bin/env python

import re
import sys
from collections import deque
from pathlib import Path


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    """Recursively get files with optional extension filter."""
    path = Path(path)
    skip_dirs = {".git", "__pycache__", ".svn", ".hg"}
    queue = deque([path])
    files = []

    while queue:
        current = queue.popleft()
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            continue

        for item in entries:
            if item.is_symlink() or not item.exists():
                continue
            if item.is_dir():
                if item.name not in skip_dirs:
                    queue.append(item)
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


def clean_transcript(content: bytes) -> str:
    """Clean terminal transcript content in a single pass."""
    # Comprehensive ANSI escape sequence removal
    # Covers: CSI sequences, OSC sequences, DCS, SOS, PM, APC, and other escapes
    ansi_pattern = re.compile(
        b"\x1b"  # ESC character
        b"(?:"
        b"\[[\d;:]*[A-Za-z]"  # CSI sequences (colors, cursor movement)
        b"|\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC sequences (window titles)
        b"|[PX^_][^\x1b]*\x1b\\"  # DCS, SOS, PM, APC
        b"|[@-_]"  # 7-bit C1 control characters
        b"|[()][\dA-Za-z]"  # Character set selection
        b")"
    )
    content = ansi_pattern.sub(b"", content)

    # Remove remaining control characters (keep newlines \n and tabs \t)
    content = re.sub(b"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", b"", content)

    # Normalize line endings
    content = re.sub(b"\r\n?|\n\r?", b"\n", content)

    # Decode with error handling
    text = content.decode("utf-8", errors="replace")

    # Remove trailing whitespace from each line
    lines = text.split("\n")
    cleaned_lines = [line.rstrip() for line in lines]
    text = "\n".join(cleaned_lines)

    # Collapse multiple blank lines (3+ becomes 2)
    text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)

    return text.strip()


def process_file(filepath: Path) -> None:
    """Process a single transcript file."""
    try:
        content = filepath.read_bytes()
        cleaned = clean_transcript(content)
        filepath.write_text(cleaned, encoding="utf-8")
        print(f"✓  {filepath.name}")
    except Exception as e:
        print(f"✗ Error processing {filepath.name}: {e}", file=sys.stderr)


def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]

    # Get files to process
    if args:
        files = []
        for arg in args:
            p = Path(arg)
            if p.is_dir():
                files.extend(get_files(p, ext=[".log", ".txt", ".md"]))
            elif p.is_file():
                files.append(p)
    else:
        files = get_files(cwd, ext=[".log", ".txt", ".md"])

    if not files:
        print("No files found to process.")
        sys.exit(0)

    print(f"Processing {len(files)} file(s)...")

    if len(files) == 1:
        process_file(files[0])
    else:
        # Use joblib for parallel processing
        try:
            from joblib import Parallel, delayed

            Parallel(n_jobs=-1, verbose=0)(delayed(process_file)(f) for f in files)
        except ImportError:
            # Fallback to sequential processing
            for f in files:
                process_file(f)

    print("Done!")


if __name__ == "__main__":
    main()
