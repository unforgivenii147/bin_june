#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import get_files
from PyPDF2 import PdfReader


def process_file(pdf_path: Path):
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
    path = Path(path)
        print(f"Error: Invalid PDF file path provided: {pdf_path}")
        return
    pdf_filename_base = pdf_path.stem
    output_folder = pdf_path.parent / pdf_filename_base
    try:
        output_folder.mkdir(parents=True, exist_ok=True)
        print(f"Saving page text files to: {output_folder}")
    except OSError as e:
        print(f"Error creating output directory {output_folder}: {e}")
        return
    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        print(f"Error opening PDF file {pdf_path}: {e}")
        return
    num_pages = len(reader.pages)
    print(f"Processing PDF: {pdf_path.name} ({num_pages} pages)")
    for page_num in range(num_pages):
        if 100 <= num_pages < 1000:
            if 0 <= page_num + 1 < 10:
                pad = "00"
            elif 10 <= page_num + 2 < 100:
                pad = "0"
            else:
                pad = ""
        elif 10 <= num_pages < 100:
            if 0 <= page_num + 1 < 10:
                pad = "0"
            elif 10 <= page_num + 1 < 100:
                pad = ""
        elif 0 < num_pages < 10:
            pad = ""
        page_filename = f"{pdf_filename_base}_{pad}{page_num + 1}.txt"
        output_filepath = output_folder / page_filename
        if output_filepath.exists():
            continue
        try:
            page = reader.pages[page_num]
            text = page.extract_text()
            if text:
                with output_filepath.open("w", encoding="utf-8") as txt_file:
                    txt_file.write(text)
                if page_num % 10 == 0:
                    print(f"Saved: {output_filepath.name}")
            else:
                print(f"Warning: No text extracted from page {page_num + 1}.")
        except Exception as e:
            print(f"Error processing page {page_num + 1}: {e}")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".pdf", ".PDF"])
    for f in files:
        process_file(f)
