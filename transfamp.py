#!/data/data/com.termux/files/home/.local/bin/python
"""
Translate Persian text files to English using deep_translator.
Each file contains one Persian word per line.
Results saved as JSON files with fa:en mappings.
Uses pathlib and parallel processing.
"""

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from deep_translator import GoogleTranslator

def translate_file(file_path: Path) -> tuple[Path, dict]:
    """
    Translate a single file's content from Persian to English.

    Args:
        file_path: Path to the input file

    Returns:
        Tuple of (output_path, translations_dict)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            print(f"⚠️  Empty file: {file_path.name}")
            return file_path, {}

        translator = GoogleTranslator(source="fa", target="en")
        translated_text = translator.translate(content)

        original_lines = [line.strip() for line in content.split("\n") if line.strip()]
        translated_lines = [line.strip() for line in translated_text.split("\n") if line.strip()]

        if len(original_lines) != len(translated_lines):
            translations = {}
            for i, line in enumerate(original_lines):
                if line:
                    try:
                        translated = GoogleTranslator(source="fa", target="en").translate(line)
                        translations[line] = translated
                    except Exception as e:
                        translations[line] = f"TRANSLATION_ERROR: {str(e)}"
                        print(f"  ⚠️  Error translating line {i + 1} in {file_path.name}: {e}")
        else:
            translations = dict(zip(original_lines, translated_lines))

        print(f"✅ Translated: {file_path.name} ({len(translations)} words)")
        return file_path, translations

    except Exception as e:
        print(f"❌ Error processing {file_path.name}: {e}")
        return file_path, {}

def save_translation(input_path: Path, translations: dict, output_dir: Path = None):
    """
    Save translations to a JSON file.

    Args:
        input_path: Original input file path
        translations: Dictionary of {fa: en} translations
        output_dir: Directory to save JSON files (default: same as input)
    """
    if output_dir is None:
        output_dir = input_path.parent

    output_dir.mkdir(parents=True, exist_ok=True)

    output_filename = input_path.stem + "_translations.json"
    output_path = output_dir / output_filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved: {output_path.name}")
    return output_path

def main():
    """Main function to orchestrate the translation process."""

    current_dir = Path(".")
    max_workers = 4
    output_dir = Path("./translations")

    text_files = list(current_dir.glob("*.txt"))

    if not text_files:
        print("❌ No .txt files found in the current directory")
        print("   If your files have a different extension, modify the glob pattern")
        return

    print(f"📚 Found {len(text_files)} file(s) to translate")
    print(f"🚀 Starting translation with {max_workers} parallel workers")
    print("-" * 50)

    start_time = time.time()
    successful = 0
    failed = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(translate_file, file_path): file_path for file_path in text_files}

        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                input_path, translations = future.result()

                if translations:
                    save_translation(input_path, translations, output_dir)
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                print(f"❌ Failed to process {file_path.name}: {e}")
                failed += 1

    elapsed_time = time.time() - start_time

    print("\n" + "=" * 50)
    print("✨ Translation complete!")
    print(f"   ✅ Successful: {successful} files")
    if failed > 0:
        print(f"   ❌ Failed: {failed} files")
    print(f"   ⏱️  Time elapsed: {elapsed_time:.2f} seconds")
    print(f"   📁 Output directory: {output_dir.absolute()}")

if __name__ == "__main__":
    main()
