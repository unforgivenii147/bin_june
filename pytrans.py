#!/data/data/com.termux/files/usr/bin/env python


import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path

import langdetect
from deep_translator import GoogleTranslator
from langdetect import DetectorFactory
from tqdm import tqdm

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


DetectorFactory.seed = 0
MAX_CHARS = 5000
TIMEOUT_PER_FILE = 60
SUPPORTED_EXTENSIONS = {".txt", ".md", ".rst", ".text", ".log"}


def get_output_filename(input_path: Path):
    if input_path.is_file():
        return input_path.parent / f"{input_path.stem}.en{input_path.suffix}"
    else:
        return input_path


def is_english(text: str, threshold=0.9) -> bool:
    try:
        if len(text.strip()) < 20:
            return False
        sample = text[:2000] if len(text) > 2000 else text
        detected_lang = langdetect.detect(sample)
        if detected_lang == "en":
            try:
                probabilities = langdetect.detect_langs(sample)
                for prob in probabilities:
                    if prob.lang == "en" and prob.prob >= threshold:
                        return True
            except:
                return True
        return False
    except:
        return False


def load_file(input_file) -> str:
    encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
    for encoding in encodings:
        try:
            with Path(input_file).open(encoding=encoding) as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            continue
    msg = f"Could not read file {input_file} with any encoding"
    raise OSError(msg)


def save_file(output_file, content: str) -> None:
    Path(output_file).write_text(content, encoding="utf-8")


def find_chunk_boundary(text, max_chars):
    if len(text) <= max_chars:
        return len(text)
    search_area = text[:max_chars]
    for delimiter in ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]:
        last_pos = search_area.rfind(delimiter)
        if last_pos > 0:
            return last_pos + len(delimiter)
    return max_chars


def chunk_text(text: str, max_chars: int):
    chunks = []
    pos = 0
    while pos < len(text):
        remaining = text[pos:]
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        chunk_end = find_chunk_boundary(remaining, max_chars)
        chunks.append(remaining[:chunk_end])
        pos += chunk_end
    return chunks


def translate_chunk(text: str, source_lang="auto", timeout=10) -> str:

    def _translate() -> str:
        translator = GoogleTranslator(source=source_lang, target="en")
        return translator.translate(text)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_translate)
        try:
            translated = future.result(timeout=timeout)
            return translated
        except FuturesTimeoutError:
            raise TimeoutError(f"Translation timeout after {timeout} seconds")


def translate_file(input_file, source_lang: str = "auto", timeout_per_chunk: int = 10) -> str | None:
    print(f"[INFO] Reading file: {input_file}")
    content = load_file(input_file)
    content_length = len(content)
    if not content.strip():
        print(f"[SKIP] File is empty: {input_file}")
        return None
    if is_english(content):
        print(f"[SKIP] File appears to be already in English: {input_file}")
        return None
    print(f"[INFO] File size: {content_length} characters")
    if content_length <= MAX_CHARS:
        print(f"[INFO] Content fits in single request ({content_length} chars)")
        print("[INFO] Translating...")
        try:
            translated = translate_chunk(content, source_lang, timeout_per_chunk)
            print(f"[INFO] Translation successful")
            return translated
        except TimeoutError as e:
            print(f"[ERROR] {e}")
            raise
    else:
        chunks = chunk_text(content, MAX_CHARS)
        total_chunks = len(chunks)
        print(f"[INFO] Content split into {total_chunks} chunks")
        translated_chunks = []
        pbar = tqdm(total=total_chunks, desc=f"Translating {input_file.name}", unit="chunk")
        try:
            for i, chunk in enumerate(chunks):
                print(f"\n[INFO] Translating chunk {i + 1}/{total_chunks} ({len(chunk)} chars)...")
                try:
                    translated_chunk = translate_chunk(chunk, source_lang, timeout_per_chunk)
                    if i < total_chunks - 1:
                        time.sleep(2)
                    translated_chunks.append(translated_chunk)
                except TimeoutError as e:
                    print(f"[WARN] Timeout on chunk {i + 1}: {e}")
                    translated_chunks.append(chunk)
                except Exception as e:
                    print(f"[ERROR] Failed to translate chunk {i + 1}: {e}")
                    translated_chunks.append(chunk)
                pbar.update(1)
        finally:
            pbar.close()
        return "".join(translated_chunks)


def process_single_file(input_file: Path, source_lang: str, timeout: int) -> bool | None:

    def _process() -> str | None:
        return translate_file(input_file, source_lang, timeout // 10)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_process)
        try:
            result = future.result(timeout=timeout)
            if result:
                output_file = get_output_filename(Path(input_file))
                save_file(output_file, result)
                print(f"[SUCCESS] Translated: {input_file} -> {output_file}")
                return True
            elif result is None:
                print(f"[SKIPPED] {input_file} (already English or empty)")
                return False
        except FuturesTimeoutError:
            print(f"[TIMEOUT] {input_file} exceeded {timeout} seconds, moving to next file")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to process {input_file}: {e}")
            return False


def process_folder(folder_path: Path, source_lang: str, timeout: int, pattern="*") -> None:
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"[ERROR] Not a directory: {folder_path}")
        return
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(folder.glob(f"*{ext}"))
        files.extend(folder.glob(f"**/*{ext}"))
    if not files:
        print(f"[WARN] No supported text files found in {folder_path}")
        print(f"Supported extensions: {', '.join(SUPPORTED_EXTENSIONS)}")
        return
    print(f"[INFO] Found {len(files)} file(s) to process")
    results = {"success": 0, "skipped": 0, "timeout": 0, "failed": 0}
    for i, file in enumerate(files, 1):
        print(f"\n{'=' * 60}")
        print(f"Processing {i}/{len(files)}: {file.name}")
        print(f"{'=' * 60}")
        result = process_single_file(file, source_lang, timeout)
        if result is True:
            results["success"] += 1
        elif result is False:
            results["timeout"] += 1
        else:
            results["failed"] += 1
    print(f"\n{'=' * 60}")
    print("PROCESSING SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total files: {len(files)}")
    print(f"Successfully translated: {results['success']}")
    print(f"Skipped (already English): {results['skipped']}")
    print(f"Timed out: {results['timeout']}")
    print(f"Failed: {results['failed']}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python translate_file.py <input_file_or_folder> [source_language] [--timeout SECONDS]")
        print("\nExamples:")
        print("  python translate_file.py document.txt")
        print("  python translate_file.py document.txt fa")
        print("  python translate_file.py /path/to/folder fa")
        print("  python translate_file.py /path/to/folder --timeout 120")
        print("  python translate_file.py document.txt --timeout 90")
        print("\nOptions:")
        print("  --timeout SECONDS  Timeout per file (default: 60 seconds)")
        print("\nSupported languages: auto, en, fa, fr, de, es, it, pt, ru, zh, ja, ko, ar, etc.")
        print("\nFeatures:")
        print("  - Auto-skips files already in English")
        print("  - Folder processing with subdirectory support")
        print("  - Timeout protection per file")
        print(f"  - Supported extensions: {', '.join(SUPPORTED_EXTENSIONS)}")
        sys.exit(1)
    input_path = sys.argv[1]
    source_lang = "auto"
    timeout = TIMEOUT_PER_FILE
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--timeout" and i + 1 < len(sys.argv):
            try:
                timeout = int(sys.argv[i + 1])
                i += 2
            except ValueError:
                print(f"[ERROR] Invalid timeout value: {sys.argv[i + 1]}")
                sys.exit(1)
        else:
            source_lang = sys.argv[i]
            i += 1
    input_path_obj = Path(input_path)
    try:
        if input_path_obj.is_dir():
            process_folder(input_path_obj, source_lang, timeout)
        elif input_path_obj.is_file():
            result = process_single_file(input_path_obj, source_lang, timeout)
            if result is None:
                print(f"[INFO] File skipped or already in English")
        else:
            print(f"[ERROR] Path does not exist: {input_path}")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Processing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
