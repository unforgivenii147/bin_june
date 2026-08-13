#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
import logging
from datetime import datetime


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)


def load_existing_translations(json_path: str) -> Dict[str, str]:
    """Load existing translations from JSON file if it exists."""
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, dict):
                    logger.info(f"Loaded {len(existing_data)} existing translations from {json_path}")
                    return existing_data
                else:
                    logger.warning(f"Existing {json_path} is not a valid dictionary format")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load existing JSON file: {e}")
    return {}


def load_failed_words(failed_path: str) -> Set[str]:
    """Load existing failed words from file if it exists."""
    if os.path.exists(failed_path):
        try:
            with open(failed_path, "r", encoding="utf-8") as f:
                failed_words = {line.strip() for line in f if line.strip()}
                logger.info(f"Loaded {len(failed_words)} existing failed words")
                return failed_words
        except IOError as e:
            logger.warning(f"Could not load failed words file: {e}")
    return set()


def process_file_pair(fa_path: Path, en_path: Path) -> Tuple[Dict[str, str], Set[str], List[str]]:
    """Process a single pair of FA/EN files."""
    translations = {}
    failed = set()
    warnings = []

    try:
        with open(fa_path, "r", encoding="utf-8") as f_fa, open(en_path, "r", encoding="utf-8") as f_en:
            fa_lines = [line.strip() for line in f_fa if line.strip()]
            en_lines = [line.strip() for line in f_en if line.strip()]

        if len(fa_lines) != len(en_lines):
            warning_msg = (
                f"Line count mismatch: {fa_path.name} ({len(fa_lines)} lines) "
                f"vs {en_path.name} ({len(en_lines)} lines). "
                f"Processing matching lines only."
            )
            warnings.append(warning_msg)
            logger.warning(warning_msg)

        for fa_word, en_word in zip(fa_lines, en_lines, strict=False):
            if not fa_word or not en_word:
                continue
            if fa_word == en_word:
                failed.add(fa_word)
            else:
                translations[fa_word] = en_word

        return translations, failed, warnings

    except (IOError, OSError) as e:
        logger.error(f"Error reading files {fa_path.name} or {en_path.name}: {e}")
        return {}, set(), [f"Error: {e}"]
    except Exception as e:
        logger.error(f"Unexpected error processing {fa_path.name}: {e}")
        return {}, set(), [f"Unexpected error: {e}"]


def merge_translations(src_dir: str = "."):
    """Main function to merge FA-EN translations."""

    output_json = "dic_fa_en.json"
    output_failed = "failed-fa.txt"

    translations = load_existing_translations(output_json)
    failed_words = load_failed_words(output_failed)
    processed_files = set()
    total_new_translations = 0

    if not os.path.isdir(src_dir):
        logger.error(f"Source directory '{src_dir}' does not exist")
        return

    try:
        all_files = sorted([f for f in os.listdir(src_dir) if f.endswith(".txt")])
    except OSError as e:
        logger.error(f"Cannot read directory {src_dir}: {e}")
        return

    fa_files = [f for f in all_files if not f.endswith("_en.txt")]

    if not fa_files:
        logger.warning(f"No FA files found in {src_dir}")
        return

    logger.info(f"Found {len(fa_files)} FA files to process")

    for fa_file in fa_files:
        base_name = fa_file[:-4]
        en_file = f"{base_name}_en.txt"

        fa_path = Path(src_dir) / fa_file
        en_path = Path(src_dir) / en_file

        if not en_path.exists():
            logger.warning(f"Skipping {fa_file}: {en_file} not found")
            continue

        file_translations, file_failed, warnings = process_file_pair(fa_path, en_path)

        new_translations_count = 0
        for fa_word, en_word in file_translations.items():
            if fa_word not in translations:
                translations[fa_word] = en_word
                new_translations_count += 1
                total_new_translations += 1

        failed_words.update(file_failed)
        for fa_word in file_failed:
            if fa_word in translations:
                failed_words.discard(fa_word)

        processed_files.add(fa_file)
        processed_files.add(en_file)

        logger.info(
            f"Processed {fa_file}: "
            f"{len(file_translations)} translations "
            f"({new_translations_count} new), "
            f"{len(file_failed)} failed"
        )

    try:
        sorted_translations = dict(sorted(translations.items()))
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(sorted_translations, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(translations)} translations to {output_json}")
    except IOError as e:
        logger.error(f"Error saving translations to {output_json}: {e}")

    try:
        sorted_failed = sorted(failed_words)
        with open(output_failed, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted_failed))
        logger.info(f"Saved {len(failed_words)} failed words to {output_failed}")
    except IOError as e:
        logger.error(f"Error saving failed words to {output_failed}: {e}")

    logger.info("=" * 50)
    logger.info(f"SUMMARY:")
    logger.info(f"Files processed: {len(processed_files) // 2} pairs")
    logger.info(f"New translations added: {total_new_translations}")
    logger.info(f"Total translations in dictionary: {len(translations)}")
    logger.info(f"Total failed words: {len(failed_words)}")
    logger.info("=" * 50)


if __name__ == "__main__":
    import time

    start_time = time.time()

    try:
        merge_translations()
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error in main execution: {e}", exc_info=True)
    finally:
        elapsed_time = time.time() - start_time
        logger.info(f"Execution completed in {elapsed_time:.2f} seconds")
