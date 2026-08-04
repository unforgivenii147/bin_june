#!/data/data/com.termux/files/home/.local/bin/python
"""
Word frequency counter for text files in current directory.
Uses parallel processing for efficiency.
"""

import json
import logging
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List

from dh import get_nobinary

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def process_file(file_path: Path) -> Counter:
    """
    Process a single file and return word frequency counter.
    """
    word_counter = Counter()

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Extract words: lowercase, remove punctuation, split on whitespace
        words = re.findall(r"\b[a-z]+\b", content.lower())
        word_counter.update(words)

        logger.debug(f"Processed {file_path.name}: {len(words)} words found")

    except Exception as e:
        logger.warning(f"Failed to process {file_path}: {e}")

    return word_counter


def collect_text_files(directory: Path = None) -> List[Path]:
    """
    Collect all text files from the specified directory.
    """
    if directory is None:
        directory = Path.cwd()

    text_files = get_nobinary(directory)

    logger.info(f"Found {len(text_files)} text files to process")
    return text_files


def process_files_parallel(file_paths: List[Path], max_workers: int = None) -> Counter:
    """
    Process multiple files in parallel and merge word counts.
    """
    total_counter = Counter()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_file, file_path): file_path for file_path in file_paths}

        # Collect results as they complete
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                file_counter = future.result()
                total_counter.update(file_counter)
                logger.debug(f"Completed processing {file_path.name}")
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")

    return total_counter


def save_results_json(counter: Counter, output_file: Path):
    """
    Save word count results to JSON file.
    """
    # Convert Counter to sorted dictionary by frequency (descending)
    sorted_words = dict(sorted(counter.items(), key=lambda x: (-x[1], x[0])))

    # Prepare the output structure
    results = {
        "metadata": {
            "total_words": sum(counter.values()),
            "unique_words": len(counter),
            "timestamp": import_datetime().isoformat(),
        },
        "word_counts": sorted_words,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"Results saved to {output_file}")


def import_datetime():
    """Import datetime only when needed."""
    from datetime import datetime

    return datetime.now()


def main():
    """
    Main execution function.
    """
    # Configuration
    directory = Path.cwd()  # Current directory
    output_file = Path("counter.json")
    max_workers = None  # None means use all available CPU cores

    logger.info(f"Starting word frequency analysis in {directory}")

    # Collect text files
    text_files = collect_text_files(directory)

    if not text_files:
        logger.warning("No text files found in the current directory!")
        # Create empty results file
        save_results_json(Counter(), output_file)
        return

    # Process files in parallel
    logger.info(f"Processing {len(text_files)} files using parallel processing...")
    total_counter = process_files_parallel(text_files, max_workers)

    # Calculate statistics
    unique_words = len(total_counter)
    total_words = sum(total_counter.values())

    # Save results as JSON
    save_results_json(total_counter, output_file)

    # Print summary
    logger.info(f"Analysis complete!")
    logger.info(f"Total words found: {total_words}")
    logger.info(f"Unique words found: {unique_words}")

    # Show top 10 most common words
    print("\n" + "=" * 50)
    print("Top 10 Most Common Words:")
    print("-" * 30)
    for word, count in total_counter.most_common(10):
        print(f"{word:<20} {count:>8}")
    print("=" * 50)
    print(f"\nFull results saved to: {output_file.absolute()}")


if __name__ == "__main__":
    main()
