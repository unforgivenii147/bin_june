#!/data/data/com.termux/files/usr/bin/env python
"""
Text file chunker with parallel processing.
Splits text files into chunks (< 5000 chars) while respecting word and sentence boundaries.
"""

import argparse
import re
import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Optional, Tuple

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

TARGET_CHUNK_SIZE = 4900  # Reduced to ensure final chunks stay under 5000
BUFFER_SIZE = 500  # Buffer to find word boundaries
MAX_CHUNK_SIZE = 4999  # Absolute maximum for any chunk


def find_chunk_boundary(text: str, start_pos: int, target_size: int = TARGET_CHUNK_SIZE) -> int:
    """
    Find a good chunk boundary that respects word and sentence boundaries.

    Args:
        text: Full text to chunk
        start_pos: Starting position for this chunk
        target_size: Target chunk size

    Returns:
        Position where chunk should end
    """
    # Ensure we don't go past the text
    end_pos = min(start_pos + target_size, len(text))

    # If we're at the end of the text, return it
    if end_pos >= len(text):
        return len(text)

    # Look for sentence boundary first (prefer sentence endings)
    search_start = max(start_pos, end_pos - BUFFER_SIZE)
    search_text = text[search_start : end_pos + BUFFER_SIZE]

    # Try to find sentence endings: . ! ? followed by space or newline
    sentence_pattern = r"[.!?]\s+"
    matches = list(re.finditer(sentence_pattern, search_text))

    if matches:
        # Use the last match before our target
        for match in reversed(matches):
            absolute_pos = search_start + match.end()
            if absolute_pos <= end_pos + BUFFER_SIZE and absolute_pos > end_pos - BUFFER_SIZE:
                return absolute_pos

    # Fall back to word boundary
    # Look backwards from end_pos for a space/newline
    for i in range(end_pos, max(start_pos, end_pos - BUFFER_SIZE), -1):
        if i < len(text) and text[i] in (" ", "\n", "\t"):
            return i + 1

    # If no good boundary found, split at target_size
    return end_pos


def split_text_into_chunks(text: str) -> List[str]:
    """
    Split text into chunks respecting word and sentence boundaries.
    Ensures all chunks are < 5000 characters.

    Args:
        text: Text to split

    Returns:
        List of text chunks
    """
    chunks = []
    pos = 0

    while pos < len(text):
        # Find where this chunk should end
        chunk_end = find_chunk_boundary(text, pos)

        # Extract chunk and strip whitespace
        chunk = text[pos:chunk_end].strip()

        if chunk:  # Only add non-empty chunks
            # Verify chunk is under max size
            if len(chunk) > MAX_CHUNK_SIZE:
                # Force split if somehow chunk is still too large
                chunk = chunk[:MAX_CHUNK_SIZE].rsplit(" ", 1)[0]

            chunks.append(chunk)

        pos = chunk_end

    return chunks


def process_file(file_path: Path, output_dir: Path) -> Tuple[str, int, Optional[str]]:
    """
    Process a single file and save chunks.

    Args:
        file_path: Path to file to process
        output_dir: Directory to save chunks

    Returns:
        Tuple of (filename, num_chunks, error_message or None)
    """
    try:
        # Read file
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        # Skip empty files
        if not text.strip():
            return (file_path.name, 0, None)

        # Split into chunks
        chunks = split_text_into_chunks(text)

        if not chunks:
            return (file_path.name, 0, None)

        # Save chunks
        stem = file_path.stem
        suffix = file_path.suffix

        for i, chunk in enumerate(chunks, 1):
            chunk_filename = f"{stem}_{i}{suffix}"
            chunk_path = output_dir / chunk_filename

            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(chunk)

        return (file_path.name, len(chunks), None)

    except Exception as e:
        return (file_path.name, 0, str(e))


def get_text_files(paths: List[Path]) -> List[Path]:
    """
    Get all text files from given paths (files or directories).

    Args:
        paths: List of file or directory paths

    Returns:
        List of text file paths
    """
    text_files = []
    text_extensions = {".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".xml"}

    for path in paths:
        if path.is_file():
            # Single file - include it if text-like
            if path.suffix.lower() in text_extensions or path.suffix == "":
                text_files.append(path)
        elif path.is_dir():
            # Directory - recursively find text files
            for file in path.rglob("*"):
                if file.is_file() and file.suffix.lower() in text_extensions:
                    text_files.append(file)

    return text_files


def main():
    parser = argparse.ArgumentParser(
        description="Split text files into chunks (< 5000 chars) respecting word/sentence boundaries."
    )
    parser.add_argument("inputs", nargs="*", help="Files or directories to process (default: current directory)")
    parser.add_argument("-o", "--output", default="output", help="Output directory for chunks (default: output)")
    parser.add_argument(
        "-j", "--jobs", type=int, default=cpu_count(), help=f"Number of parallel jobs (default: {cpu_count()})"
    )

    args = parser.parse_args()

    # Determine input paths
    if args.inputs:
        input_paths = [Path(p) for p in args.inputs]
    else:
        input_paths = [Path.cwd()]

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True, parents=True)

    # Get all text files
    text_files = get_text_files(input_paths)

    if not text_files:
        print("No text files found.")
        return 1

    print(f"Found {len(text_files)} text file(s)")
    print(f"Processing with {args.jobs} parallel job(s)...")
    print(f"Target chunk size: < 5000 characters")

    # Process files in parallel
    with Pool(args.jobs) as pool:
        results = pool.starmap(process_file, [(f, output_dir) for f in text_files])

    # Print results
    total_chunks = 0
    errors = 0

    print("\nResults:")
    print("-" * 60)
    for filename, num_chunks, error in results:
        if error:
            print(f"❌ {filename}: {error}")
            errors += 1
        else:
            print(f"✓ {filename}: {num_chunks} chunk(s)")
            total_chunks += num_chunks

    print("-" * 60)
    print(f"Total chunks created: {total_chunks}")
    print(f"Output directory: {output_dir.resolve()}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
