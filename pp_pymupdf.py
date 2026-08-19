#!/data/data/com.termux/files/home/.local/bin/python
"""
Ultra-fast PDF text extraction using PyMuPDF
Processes files sequentially, pages in parallel
"""

import sys
from pathlib import Path
import fitz  # PyMuPDF
from joblib import Parallel, delayed


def extract_page_batch(pdf_path, page_numbers, output_dir):
    """Extract a batch of pages from a PDF"""
    results = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in page_numbers:
            page = doc[page_num - 1]
            text = page.get_text("text", sort=True)  # sort for better reading order
            page_file = output_dir / f"page_{page_num:03d}.txt"
            page_file.write_text(text, encoding="utf-8")
            results.append((page_num, page_file))
        doc.close()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    return results


def extract_pages_from_pdf_optimized(pdf_path, n_jobs=4):
    """Optimized extraction with batched page processing"""
    pdf_path = Path(pdf_path)
    output_dir = pdf_path.parent / pdf_path.stem
    output_dir.mkdir(exist_ok=True)

    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()

        # Split pages into batches for better performance
        batch_size = max(1, total_pages // n_jobs)
        batches = []
        for i in range(0, total_pages, batch_size):
            end = min(i + batch_size, total_pages)
            batches.append(list(range(i + 1, end + 1)))

        # Process batches in parallel
        all_results = Parallel(n_jobs=n_jobs, backend="threading")(
            delayed(extract_page_batch)(pdf_path, batch, output_dir) for batch in batches
        )

        # Flatten results
        results = [item for sublist in all_results for item in sublist]
        return results

    except Exception as e:
        print(f"Error processing {pdf_path}: {e}", file=sys.stderr)
        return []
